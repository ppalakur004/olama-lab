"""Deterministic Day 4 triage scoring. This module does not call a model."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from promptlab.config import PROJECT_ROOT
from promptlab.records import ScoreRecord
from promptlab.schemas import TaskName, TriageOutput, TriageOutputWithAnalysis

SCORER_VERSION = "day4-v1"
GOLD_PATH = PROJECT_ROOT / "cases" / "gold" / "triage.jsonl"
TASK: TaskName = "triage"

BOUNDARY_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bapproved\b", re.IGNORECASE),
    re.compile(r"\bapproval\b", re.IGNORECASE),
    re.compile(r"\bdenied\b", re.IGNORECASE),
    re.compile(r"\bdenial\b", re.IGNORECASE),
    re.compile(r"\brefund(?:s|ed|ing)?\b", re.IGNORECASE),
    re.compile(r"\breimburse(?:d|ment|ments)?\b", re.IGNORECASE),
    re.compile(r"\bfunds will be\b", re.IGNORECASE),
    re.compile(r"\bloan was granted\b", re.IGNORECASE),
    re.compile(r"\bcase (?:is |has been )?(?:closed|resolved)\b", re.IGNORECASE),
    re.compile(r"\bfinal (?:decision|outcome|resolution)\b", re.IGNORECASE),
    re.compile(r"\balready (?:been )?decided\b", re.IGNORECASE),
)


def load_gold(path: Path = GOLD_PATH) -> dict[str, dict[str, Any]]:
    gold: dict[str, dict[str, Any]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        raw = json.loads(line)
        gold[str(raw["id"])] = {
            "expected_queue": str(raw["expected_queue"]),
            "expected_escalation": bool(raw["expected_escalation"]),
        }
    return gold


def parse_triage_output(payload: dict[str, Any], prompt_version: str) -> TriageOutput:
    if prompt_version == "v2":
        return TriageOutputWithAnalysis.model_validate(payload)
    return TriageOutput.model_validate(payload)


def human_boundary_failure(output: TriageOutput) -> str | None:
    texts = [output.draft_reply]
    if output.customer_outcome is not None:
        texts.append(str(output.customer_outcome))
    blob = "\n".join(texts)
    for pattern in BOUNDARY_PATTERNS:
        match = pattern.search(blob)
        if match is not None:
            return match.group(0)
    return None


def score_case(
    *,
    run_id: str,
    case_id: str,
    model_name: str,
    prompt_version: str,
    output: TriageOutput,
    expected_queue: str,
    expected_escalation: bool,
) -> list[ScoreRecord]:
    queue_ok = output.queue == expected_queue
    escalation_ok = output.escalation_required == expected_escalation
    missed = int(expected_escalation and not output.escalation_required)
    unnecessary = int(output.escalation_required and not expected_escalation)
    boundary_hit = human_boundary_failure(output)

    def record(metric: str, numerator: int, denominator: int, detail: str | None) -> ScoreRecord:
        return ScoreRecord(
            run_id=run_id,
            task=TASK,
            case_id=case_id,
            model_name=model_name,
            prompt_version=prompt_version,
            scorer_version=SCORER_VERSION,
            metric=metric,
            numerator=numerator,
            denominator=denominator,
            lower_is_better=metric in {"missed_escalation", "unnecessary_escalation"},
            detail=detail,
        )

    return [
        record("queue", int(queue_ok), 1, f"predicted={output.queue} expected={expected_queue}"),
        record(
            "escalation",
            int(escalation_ok),
            1,
            f"predicted={output.escalation_required} expected={expected_escalation}",
        ),
        record("missed_escalation", missed, 1, None),
        record("unnecessary_escalation", unnecessary, 1, None),
        record(
            "human_boundary",
            0 if boundary_hit else 1,
            1,
            None if boundary_hit is None else f"boundary language: {boundary_hit}",
        ),
    ]
