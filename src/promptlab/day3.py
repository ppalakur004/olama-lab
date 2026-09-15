"""Day 3 harness: structured summarize + extract with one local model."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel

from promptlab.adapters.base import CompletionRequest
from promptlab.adapters.ollama import OllamaAdapter
from promptlab.config import PROJECT_ROOT, Settings
from promptlab.schemas import (
    PolicyExtraction,
    SummarizationOutput,
    schema_description,
)
from promptlab.structured import complete_structured

TEMPERATURE = 0.0
MAX_OUTPUT_TOKENS = 2048
SUMMARIZE_PROMPT = PROJECT_ROOT / "src" / "prompts" / "summarize.v1.md"
EXTRACT_PROMPT = PROJECT_ROOT / "src" / "prompts" / "extract.v2.md"
SUMMARIZE_CASES = PROJECT_ROOT / "cases" / "summarization.jsonl"
EXTRACT_CASES = PROJECT_ROOT / "cases" / "extraction.jsonl"


def load_cases(path: Path) -> list[dict[str, str]]:
    cases: list[dict[str, str]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        raw: dict[str, Any] = json.loads(line)
        cases.append({"id": str(raw["id"]), "source": str(raw["source"])})
    return cases


def render_prompt(template: str, document_text: str, schema: type[BaseModel]) -> str:
    return template.replace("{schema_description}", schema_description(schema)).replace(
        "{document_text}", document_text
    )


def build_request(
    *,
    task: Literal["summarization", "extraction"],
    case_id: str,
    prompt_id: str,
    prompt_version: str,
    prompt_text: str,
) -> CompletionRequest:
    return CompletionRequest(
        task=task,
        case_id=case_id,
        prompt_id=prompt_id,
        prompt_version=prompt_version,
        system="",
        user_content=prompt_text,
        temperature=TEMPERATURE,
        max_output_tokens=MAX_OUTPUT_TOKENS,
    )


def run_batch(
    adapter: OllamaAdapter,
    run_id: str,
    *,
    task: Literal["summarization", "extraction"],
    prompt_id: str,
    prompt_version: str,
    template: str,
    schema: type[BaseModel],
    cases: list[dict[str, str]],
) -> tuple[int, int]:
    ok = 0
    for case in cases:
        request = build_request(
            task=task,
            case_id=case["id"],
            prompt_id=prompt_id,
            prompt_version=prompt_version,
            prompt_text=render_prompt(template, case["source"], schema),
        )
        try:
            complete_structured(adapter, request, schema, run_id)
            ok += 1
            status = "validated"
        except ValueError as exc:
            status = f"failed ({exc})"
        print(f"{adapter.model_id} {task} {case['id']} {status}")
    return ok, len(cases)


def main() -> None:
    settings = Settings.from_env()
    run_id = f"day3-{uuid4().hex[:8]}"
    adapter = OllamaAdapter(model_id=settings.models["mistral"].model_id)
    summarize_template = SUMMARIZE_PROMPT.read_text(encoding="utf-8")
    extract_template = EXTRACT_PROMPT.read_text(encoding="utf-8")

    print(f"run_id={run_id} model={adapter.model_id}")
    s_ok, s_n = run_batch(
        adapter,
        run_id,
        task="summarization",
        prompt_id="summarize",
        prompt_version="v1",
        template=summarize_template,
        schema=SummarizationOutput,
        cases=load_cases(SUMMARIZE_CASES),
    )
    e_ok, e_n = run_batch(
        adapter,
        run_id,
        task="extraction",
        prompt_id="extract",
        prompt_version="v2",
        template=extract_template,
        schema=PolicyExtraction,
        cases=load_cases(EXTRACT_CASES),
    )
    print(f"summarization validated={s_ok}/{s_n}")
    print(f"extraction validated={e_ok}/{e_n}")
    print(f"appended to runs/{run_id}.jsonl")


if __name__ == "__main__":
    main()
