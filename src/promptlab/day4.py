"""Day 4 harness: triage.v1 vs triage.v2 under one local model and run_id."""

from __future__ import annotations

import json
import statistics
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ValidationError

from promptlab.adapters.base import CompletionRequest
from promptlab.adapters.ollama import OllamaAdapter
from promptlab.config import PROJECT_ROOT, Settings
from promptlab.prompts import load, render_user
from promptlab.records import ScoreRecord, append_record
from promptlab.schemas import (
    TriageOutput,
    TriageOutputWithAnalysis,
    schema_description,
)
from promptlab.scoring import load_gold, parse_triage_output, score_case
from promptlab.structured import _load_json, complete_structured
from promptlab.usage import CallRecord

TEMPERATURE = 0.0
MAX_OUTPUT_TOKENS = 1024
TRIAGE_CASES = PROJECT_ROOT / "cases" / "triage.jsonl"
DOCS_DIR = PROJECT_ROOT / "docs"
NOTES_PATH = DOCS_DIR / "day4-notes.md"
RUN_COPY_PATH = DOCS_DIR / "day4-run.jsonl"
SCORES_PATH = DOCS_DIR / "day4-scores.jsonl"


def load_cases(path: Path) -> list[dict[str, str]]:
    cases: list[dict[str, str]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        raw: dict[str, Any] = json.loads(line)
        cases.append({"id": str(raw["id"]), "source": str(raw["source"])})
    return cases


def load_call_records(path: Path) -> list[CallRecord]:
    records: list[CallRecord] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            records.append(CallRecord.model_validate_json(line))
    return records


def last_parseable_output(
    records: list[CallRecord],
    *,
    case_id: str,
    prompt_version: str,
    schema: type[BaseModel],
) -> tuple[CallRecord, BaseModel] | None:
    matching = [
        row
        for row in records
        if row.case_id == case_id and row.prompt_version == prompt_version
    ]
    for row in reversed(matching):
        if not row.response_text:
            continue
        try:
            payload = _load_json(row.response_text)
            if not isinstance(payload, dict):
                continue
            parsed = schema.model_validate(payload)
        except (json.JSONDecodeError, ValidationError, TypeError, ValueError):
            continue
        return row, parsed
    return None


def run_batch(
    adapter: OllamaAdapter,
    run_id: str,
    *,
    prompt_version: str,
    schema: type[BaseModel],
    cases: list[dict[str, str]],
) -> tuple[int, int]:
    template = load("triage", prompt_version)
    variables = {"schema_description": schema_description(schema)}
    ok = 0
    for case in cases:
        user_content = render_user(template, variables, case["source"])
        request = CompletionRequest(
            task="triage",
            case_id=case["id"],
            prompt_id="triage",
            prompt_version=prompt_version,
            system=template.system,
            user_content=user_content,
            temperature=TEMPERATURE,
            max_output_tokens=MAX_OUTPUT_TOKENS,
        )
        try:
            complete_structured(adapter, request, schema, run_id)
            ok += 1
            status = "validated"
        except ValueError as exc:
            status = f"failed ({exc})"
        print(f"{adapter.model_id} triage {prompt_version} {case['id']} {status}")
    return ok, len(cases)


def score_run(
    records: list[CallRecord],
    *,
    run_id: str,
    model_name: str,
    versions: tuple[str, ...],
) -> list[ScoreRecord]:
    gold = load_gold()
    schemas: dict[str, type[BaseModel]] = {
        "v1": TriageOutput,
        "v2": TriageOutputWithAnalysis,
    }
    scores: list[ScoreRecord] = []
    for version in versions:
        schema = schemas[version]
        for case_id, expected in gold.items():
            found = last_parseable_output(
                records, case_id=case_id, prompt_version=version, schema=schema
            )
            if found is None:
                continue
            _row, parsed = found
            output = parse_triage_output(parsed.model_dump(), version)
            scores.extend(
                score_case(
                    run_id=run_id,
                    case_id=case_id,
                    model_name=model_name,
                    prompt_version=version,
                    output=output,
                    expected_queue=str(expected["expected_queue"]),
                    expected_escalation=bool(expected["expected_escalation"]),
                )
            )
    return scores


def _metric_total(scores: list[ScoreRecord], version: str, metric: str) -> tuple[int, int]:
    rows = [row for row in scores if row.prompt_version == version and row.metric == metric]
    return sum(row.numerator for row in rows), sum(row.denominator for row in rows)


def _last_success_by_case(records: list[CallRecord], version: str) -> dict[str, CallRecord]:
    by_case: dict[str, CallRecord] = {}
    for row in records:
        if row.prompt_version != version or row.error_type:
            continue
        by_case[row.case_id] = row
    return by_case


def write_notes(
    records: list[CallRecord],
    scores: list[ScoreRecord],
    *,
    run_id: str,
    model_id: str,
) -> str:
    gold = load_gold()
    case_ids = list(gold)
    v1_last = _last_success_by_case(records, "v1")
    v2_last = _last_success_by_case(records, "v2")

    def block(version: str) -> list[str]:
        queue_n, queue_d = _metric_total(scores, version, "queue")
        esc_n, esc_d = _metric_total(scores, version, "escalation")
        missed, _ = _metric_total(scores, version, "missed_escalation")
        unnecessary, _ = _metric_total(scores, version, "unnecessary_escalation")
        bound_n, bound_d = _metric_total(scores, version, "human_boundary")
        return [
            f"triage.{version}",
            f"queue correct: {queue_n}/{queue_d}",
            f"escalation correct: {esc_n}/{esc_d}",
            f"missed escalations: {missed}",
            f"unnecessary escalations: {unnecessary}",
            f"human-boundary passes: {bound_n}/{bound_d}",
        ]

    queues_changed = 0
    token_lines: list[str] = []
    v1_tokens = 0
    v2_tokens = 0
    for case_id in case_ids:
        left = v1_last.get(case_id)
        right = v2_last.get(case_id)
        if left is None or right is None:
            continue
        v1_tokens += left.output_tokens
        v2_tokens += right.output_tokens
        token_lines.append(
            f"{case_id}: v1={left.output_tokens} v2={right.output_tokens} "
            f"delta={right.output_tokens - left.output_tokens}"
        )
        try:
            raw_v1 = _load_json(left.response_text or "")
            raw_v2 = _load_json(right.response_text or "")
            if not isinstance(raw_v1, dict) or not isinstance(raw_v2, dict):
                continue
            q1 = parse_triage_output(raw_v1, "v1").queue
            q2 = parse_triage_output(raw_v2, "v2").queue
        except (json.JSONDecodeError, ValidationError, TypeError, ValueError):
            continue
        if q1 != q2:
            queues_changed += 1

    latencies = [row.latency_ms for row in records]
    median_latency = int(statistics.median(latencies)) if latencies else 0
    max_latency = max(latencies) if latencies else 0
    token_delta = v2_tokens - v1_tokens
    queue_v1, _ = _metric_total(scores, "v1", "queue")
    queue_v2, _ = _metric_total(scores, "v2", "queue")
    if token_delta > 0 and queue_v2 <= queue_v1:
        conclusion = (
            "The v2 analysis field used more output tokens without a queue-accuracy "
            "gain that would justify the extra overhead on this 12-case set."
        )
    elif queue_v2 > queue_v1:
        conclusion = (
            "v2 gained queue accuracy on this 12-case set, but a one-case gap is not "
            "proof that the analysis field is universally better."
        )
    else:
        conclusion = (
            "v2 did not earn a routing improvement that clearly justifies extra "
            "analysis tokens on this 12-case set."
        )

    lines = [
        f"Run `{run_id}` on {model_id}, temperature 0.0, one shared run_id. "
        "Evidence is `docs/day4-run.jsonl` and `docs/day4-scores.jsonl`. "
        "Local provider/API cost is $0.00.",
        "",
        *block("v1"),
        "",
        *block("v2"),
        "",
        f"changed-queue count: {queues_changed}/12",
        f"output tokens v1 total: {v1_tokens}",
        f"output tokens v2 total: {v2_tokens}",
        f"output-token difference (v2 - v1): {token_delta}",
        "output tokens per case:",
        *[f"- {line}" for line in token_lines],
        f"median latency: {median_latency} ms",
        f"maximum latency: {max_latency} ms",
        f"observation count: {len(records)}",
        "",
        conclusion,
    ]
    text = "\n".join(lines) + "\n"
    NOTES_PATH.write_text(text, encoding="utf-8")
    return text


def main() -> None:
    settings = Settings.from_env()
    run_id = f"day4-{uuid4().hex[:8]}"
    model = settings.models["mistral"]
    adapter = OllamaAdapter(model_id=model.model_id)
    cases = load_cases(TRIAGE_CASES)

    print(f"run_id={run_id} model={adapter.model_id}")
    v1_ok, v1_n = run_batch(
        adapter,
        run_id,
        prompt_version="v1",
        schema=TriageOutput,
        cases=cases,
    )
    v2_ok, v2_n = run_batch(
        adapter,
        run_id,
        prompt_version="v2",
        schema=TriageOutputWithAnalysis,
        cases=cases,
    )
    print(f"triage.v1 validated={v1_ok}/{v1_n}")
    print(f"triage.v2 validated={v2_ok}/{v2_n}")

    run_path = Path("runs") / f"{run_id}.jsonl"
    records = load_call_records(run_path)
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    RUN_COPY_PATH.write_text(run_path.read_text(encoding="utf-8"), encoding="utf-8")

    if SCORES_PATH.exists():
        SCORES_PATH.unlink()
    scores = score_run(
        records,
        run_id=run_id,
        model_name=model.logical_name,
        versions=("v1", "v2"),
    )
    for score in scores:
        append_record(SCORES_PATH, score)

    notes = write_notes(
        records, scores, run_id=run_id, model_id=adapter.model_id
    )
    print(f"appended to {run_path}")
    print(f"copied to {RUN_COPY_PATH}")
    print(f"scores at {SCORES_PATH}")
    print(notes)


if __name__ == "__main__":
    main()
