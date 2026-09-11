"""Day 2 harness: same request against Mistral and Qwen via OllamaAdapter."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from promptlab.adapters.base import CompletionRequest
from promptlab.adapters.ollama import OllamaAdapter
from promptlab.config import PROJECT_ROOT, Settings

PROMPT_ID = "baseline"
PROMPT_VERSION = "v0"
TEMPERATURE = 0.0
MAX_OUTPUT_TOKENS = 256
CASES_PATH = PROJECT_ROOT / "cases" / "summarization.jsonl"
PROMPT_PATH = PROJECT_ROOT / "src" / "prompts" / "baseline.v0.md"


def load_system_prompt() -> str:
    template = PROMPT_PATH.read_text(encoding="utf-8")
    system, _, _ = template.partition("{document_text}")
    return system.strip()


def load_cases(path: Path) -> list[dict[str, str]]:
    cases: list[dict[str, str]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        raw: dict[str, Any] = json.loads(line)
        cases.append({"id": str(raw["id"]), "source": str(raw["source"])})
    return cases


def build_request(system: str, case: dict[str, str]) -> CompletionRequest:
    return CompletionRequest(
        task="summarization",
        case_id=case["id"],
        prompt_id=PROMPT_ID,
        prompt_version=PROMPT_VERSION,
        system=system,
        user_content=case["source"],
        temperature=TEMPERATURE,
        max_output_tokens=MAX_OUTPUT_TOKENS,
    )


def main() -> None:
    settings = Settings.from_env()
    run_id = f"day2-{uuid4().hex[:8]}"
    system = load_system_prompt()
    cases = load_cases(CASES_PATH)
    adapters = [
        OllamaAdapter(model_id=settings.models["mistral"].model_id),
        OllamaAdapter(model_id=settings.models["qwen"].model_id),
    ]

    print(f"run_id={run_id} cases={len(cases)}")
    for adapter in adapters:
        for case in cases:
            request = build_request(system, case)
            result = adapter.complete(request, run_id)
            print(
                f"{adapter.model_id} {case['id']} succeeded={result.succeeded} "
                f"error_type={result.error_type} attempts={len(result.records)}"
            )
    print(f"appended to runs/{run_id}.jsonl")


if __name__ == "__main__":
    main()
