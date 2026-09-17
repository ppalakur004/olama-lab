"""Deterministic scoring. This module does not call a model."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from promptlab.config import PII_PATTERNS, PROJECT_ROOT
from promptlab.corpus import GoldLabel
from promptlab.records import ScoreRecord
from promptlab.schemas import (
    EvidenceField,
    PolicyExtraction,
    StrictModel,
    SummarizationOutput,
    TaskName,
    TriageOutput,
    TriageOutputWithAnalysis,
)

SCORER_VERSION = "day5-v2"
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

_HEADING = re.compile(r"^\s*(\d+\.\s+\S.*?)\s*$", re.MULTILINE)

_LOWER_IS_BETTER = {
    "missed_escalation",
    "unnecessary_escalation",
    "pii_leakage",
    "missed_required_evidence",
    "invented_unsupported",
}


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
    if prompt_version == "v2" or prompt_version.endswith(".v2"):
        return TriageOutputWithAnalysis.model_validate(payload)
    return TriageOutput.model_validate(payload)


def source_sections(source: str) -> set[str]:
    """Return numbered heading lines, lowercased, from a source document."""
    return {match.group(1).casefold() for match in _HEADING.finditer(source)}


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


def _pii_hit(text: str) -> bool:
    return any(pattern.search(text) for pattern in PII_PATTERNS)


def _evidence_fields(output: StrictModel) -> dict[str, EvidenceField]:
    if isinstance(output, SummarizationOutput | PolicyExtraction):
        return output.evidence_fields()
    return {}


def _citation_matches(citation: str | None, sections: set[str]) -> bool:
    if citation is None or not citation.strip():
        return False
    return citation.strip().casefold() in sections


def _free_text(output: StrictModel) -> str:
    parts: list[str] = []
    if isinstance(output, TriageOutput):
        parts.extend([output.rationale, output.draft_reply])
        if isinstance(output, TriageOutputWithAnalysis):
            parts.append(output.analysis)
    for field in _evidence_fields(output).values():
        if isinstance(field.value, str):
            parts.append(field.value)
        elif isinstance(field.value, list):
            parts.extend(item for item in field.value if isinstance(item, str))
        if field.citation:
            parts.append(field.citation)
    return "\n".join(parts)


def _record(
    *,
    run_id: str,
    task: TaskName,
    case_id: str,
    model_name: str,
    prompt_version: str,
    metric: str,
    numerator: int,
    denominator: int,
    detail: str | None = None,
) -> ScoreRecord:
    return ScoreRecord(
        run_id=run_id,
        task=task,
        case_id=case_id,
        model_name=model_name,
        prompt_version=prompt_version,
        scorer_version=SCORER_VERSION,
        metric=metric,
        numerator=numerator,
        denominator=denominator,
        lower_is_better=metric in _LOWER_IS_BETTER,
        detail=detail,
    )


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
    gold = GoldLabel(
        id=case_id,
        task="triage",
        expected_queue=expected_queue,
        expected_escalation=expected_escalation,
    )
    return score_output(
        run_id=run_id,
        task="triage",
        case_id=case_id,
        model_name=model_name,
        prompt_version=prompt_version,
        output=output,
        gold=gold,
        source="",
    )


def _score_triage(
    *,
    run_id: str,
    case_id: str,
    model_name: str,
    prompt_version: str,
    output: TriageOutput,
    gold: GoldLabel,
) -> list[ScoreRecord]:
    expected_queue = gold.expected_queue or ""
    expected_escalation = bool(gold.expected_escalation)
    queue_ok = output.queue == expected_queue
    escalation_ok = output.escalation_required == expected_escalation
    missed = int(expected_escalation and not output.escalation_required)
    unnecessary = int(output.escalation_required and not expected_escalation)
    boundary_hit = human_boundary_failure(output)
    leaked = _pii_hit(_free_text(output))

    def rec(metric: str, numerator: int, denominator: int, detail: str | None) -> ScoreRecord:
        return _record(
            run_id=run_id,
            task="triage",
            case_id=case_id,
            model_name=model_name,
            prompt_version=prompt_version,
            metric=metric,
            numerator=numerator,
            denominator=denominator,
            detail=detail,
        )

    return [
        rec("queue", int(queue_ok), 1, f"predicted={output.queue} expected={expected_queue}"),
        rec(
            "escalation",
            int(escalation_ok),
            1,
            f"predicted={output.escalation_required} expected={expected_escalation}",
        ),
        rec("missed_escalation", missed, 1, None),
        rec("unnecessary_escalation", unnecessary, 1, None),
        rec(
            "human_boundary_compliance",
            0 if boundary_hit else 1,
            1,
            None if boundary_hit is None else f"boundary language: {boundary_hit}",
        ),
        rec("pii_leakage", int(leaked), 1, None),
    ]


def _score_evidence(
    *,
    run_id: str,
    task: TaskName,
    case_id: str,
    model_name: str,
    prompt_version: str,
    output: StrictModel,
    gold: GoldLabel,
    source: str,
) -> list[ScoreRecord]:
    fields = _evidence_fields(output)
    recoverable = list(gold.recoverable_fields)
    sections = source_sections(source)

    present_required = [
        name for name in recoverable if name in fields and fields[name].status == "present"
    ]
    missed = [
        name for name in recoverable if name in fields and fields[name].status != "present"
    ]
    other_names = [name for name in fields if name not in set(recoverable)]
    invented = [name for name in other_names if fields[name].status == "present"]
    avoided = [name for name in other_names if fields[name].status != "present"]
    cited_ok = [
        name
        for name in fields
        if fields[name].status == "present" and _citation_matches(fields[name].citation, sections)
    ]
    present_names = [name for name, field in fields.items() if field.status == "present"]
    status_ok = (
        gold.expected_status is None
        or (
            isinstance(output, SummarizationOutput | PolicyExtraction)
            and output.document_status == gold.expected_status
        )
    )
    leaked = _pii_hit(_free_text(output))

    def rec(
        metric: str, numerator: int, denominator: int, detail: str | None = None
    ) -> ScoreRecord:
        return _record(
            run_id=run_id,
            task=task,
            case_id=case_id,
            model_name=model_name,
            prompt_version=prompt_version,
            metric=metric,
            numerator=numerator,
            denominator=denominator,
            detail=detail,
        )

    rows = [
        rec("required_evidence_recall", len(present_required), len(recoverable)),
        rec("citation_correctness", len(cited_ok), len(present_names)),
        rec("unsupported_field_avoidance", len(avoided), len(other_names)),
        rec("missed_required_evidence", len(missed), len(recoverable)),
        rec("invented_unsupported", len(invented), len(other_names)),
        rec("pii_leakage", int(leaked), 1),
    ]
    if gold.expected_status is not None:
        rows.append(
            rec(
                "document_status",
                int(status_ok),
                1,
                f"predicted={getattr(output, 'document_status', None)} "
                f"expected={gold.expected_status}",
            )
        )
    return rows


def score_output(
    *,
    run_id: str,
    task: TaskName,
    case_id: str,
    model_name: str,
    prompt_version: str,
    output: StrictModel,
    gold: GoldLabel,
    source: str,
) -> list[ScoreRecord]:
    if task == "triage":
        if not isinstance(output, TriageOutput):
            raise TypeError(f"expected TriageOutput for triage, got {type(output).__name__}")
        return _score_triage(
            run_id=run_id,
            case_id=case_id,
            model_name=model_name,
            prompt_version=prompt_version,
            output=output,
            gold=gold,
        )
    return _score_evidence(
        run_id=run_id,
        task=task,
        case_id=case_id,
        model_name=model_name,
        prompt_version=prompt_version,
        output=output,
        gold=gold,
        source=source,
    )
