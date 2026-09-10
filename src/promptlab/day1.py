"""Day 1 harness: call local Mistral and append usage records."""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx

from promptlab.config import PROJECT_ROOT, Settings
from promptlab.usage import CallRecord, append_record, compute_cost

CASE_IDS: tuple[str, ...] = ("E12", "E07", "E11")
PROMPT_ID = "baseline"
PROMPT_VERSION = "v0"
TEMPERATURE = 0.0
MAX_OUTPUT_TOKENS = 256
TRUNCATION_OUTPUT_TOKENS = 8
CASES_PATH = PROJECT_ROOT / "cases" / "extraction.jsonl"
PROMPT_PATH = PROJECT_ROOT / "src" / "prompts" / "baseline.v0.md"


def load_prompt_template() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def load_cases(path: Path, case_ids: tuple[str, ...]) -> list[dict[str, str]]:
    by_id: dict[str, dict[str, str]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        raw: dict[str, Any] = json.loads(line)
        case_id = str(raw["id"])
        by_id[case_id] = {"id": case_id, "source": str(raw["source"])}
    missing = [case_id for case_id in case_ids if case_id not in by_id]
    if missing:
        raise KeyError(f"Missing extraction cases: {missing}")
    return [by_id[case_id] for case_id in case_ids]


def _as_int(value: object) -> int:
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    return 0


def _as_optional_str(value: object) -> str | None:
    if isinstance(value, str):
        return value
    return None


def call_ollama(
    *,
    base_url: str,
    model_id: str,
    prompt: str,
    temperature: float,
    num_predict: int,
) -> tuple[dict[str, object], int, str | None]:
    started = time.perf_counter()
    try:
        response = httpx.post(
            f"{base_url}/api/generate",
            json={
                "model": model_id,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "num_predict": num_predict,
                },
            },
            timeout=180.0,
        )
        latency_ms = int(round((time.perf_counter() - started) * 1000))
        if response.status_code >= 400:
            return {}, latency_ms, "HTTPStatusError"
        payload = response.json()
        if not isinstance(payload, dict):
            return {}, latency_ms, "InvalidResponseError"
        return payload, latency_ms, None
    except httpx.HTTPError as exc:
        latency_ms = int(round((time.perf_counter() - started) * 1000))
        return {}, latency_ms, type(exc).__name__


def build_record(
    *,
    run_id: str,
    model_id: str,
    case_id: str,
    attempt: int,
    temperature: float,
    max_output_tokens: int,
    payload: dict[str, object],
    latency_ms: int,
    transport_error: str | None,
) -> CallRecord:
    input_tokens = _as_int(payload.get("prompt_eval_count"))
    output_tokens = _as_int(payload.get("eval_count"))
    stop_reason = _as_optional_str(payload.get("done_reason"))
    response_text = _as_optional_str(payload.get("response"))
    error_type = transport_error
    if error_type is None and stop_reason == "length":
        error_type = "TruncatedResponseError"
    if transport_error is not None:
        response_text = None
    return CallRecord(
        record_id=str(uuid4()),
        run_id=run_id,
        timestamp=datetime.now(UTC),
        provider="ollama",
        model_id=model_id,
        task="extraction",
        case_id=case_id,
        prompt_id=PROMPT_ID,
        prompt_version=PROMPT_VERSION,
        attempt=attempt,
        temperature=temperature,
        max_output_tokens=max_output_tokens,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cached_input_tokens=None,
        latency_ms=latency_ms,
        cost_usd=compute_cost(model_id, input_tokens, output_tokens),
        stop_reason=stop_reason,
        error_type=error_type,
        response_text=response_text,
    )


def run_case(
    *,
    settings: Settings,
    model_id: str,
    run_id: str,
    case_id: str,
    prompt: str,
    attempt: int,
    max_output_tokens: int,
) -> CallRecord:
    payload, latency_ms, transport_error = call_ollama(
        base_url=settings.ollama_base_url,
        model_id=model_id,
        prompt=prompt,
        temperature=TEMPERATURE,
        num_predict=max_output_tokens,
    )
    record = build_record(
        run_id=run_id,
        model_id=model_id,
        case_id=case_id,
        attempt=attempt,
        temperature=TEMPERATURE,
        max_output_tokens=max_output_tokens,
        payload=payload,
        latency_ms=latency_ms,
        transport_error=transport_error,
    )
    append_record(record, run_id)
    return record


def main() -> None:
    settings = Settings.from_env()
    model_id = settings.models["mistral"].model_id
    run_id = f"day1-{uuid4().hex[:8]}"
    template = load_prompt_template()
    cases = load_cases(CASES_PATH, CASE_IDS)

    for case in cases:
        prompt = template.replace("{document_text}", case["source"])
        record = run_case(
            settings=settings,
            model_id=model_id,
            run_id=run_id,
            case_id=case["id"],
            prompt=prompt,
            attempt=1,
            max_output_tokens=MAX_OUTPUT_TOKENS,
        )
        print(
            f"{record.case_id} error_type={record.error_type} "
            f"stop_reason={record.stop_reason} "
            f"input={record.input_tokens} output={record.output_tokens} "
            f"latency_ms={record.latency_ms}"
        )

    long_case = next(case for case in cases if case["id"] == "E11")
    truncation_record = run_case(
        settings=settings,
        model_id=model_id,
        run_id=run_id,
        case_id=long_case["id"],
        prompt=template.replace("{document_text}", long_case["source"]),
        attempt=2,
        max_output_tokens=TRUNCATION_OUTPUT_TOKENS,
    )
    print(
        f"truncation demo E11 error_type={truncation_record.error_type} "
        f"stop_reason={truncation_record.stop_reason} "
        f"max_output_tokens={truncation_record.max_output_tokens}"
    )
    print(f"appended to runs/{run_id}.jsonl")


if __name__ == "__main__":
    main()
