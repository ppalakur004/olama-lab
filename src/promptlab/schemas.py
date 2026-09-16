from __future__ import annotations

import types
from typing import Literal, Union, get_args, get_origin

from pydantic import BaseModel, ConfigDict, Field

TaskName = Literal["triage", "summarization", "extraction"]
FieldStatus = Literal["present", "absent", "ambiguous"]
DocumentStatus = Literal["valid", "contradictory", "superseded", "unsupported"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EvidenceField(StrictModel):
    value: str | list[str] | None
    status: FieldStatus
    citation: str | None = None


class TriageOutput(StrictModel):
    queue: Literal[
        "card_dispute",
        "fraud_report",
        "account_servicing",
        "lending",
        "complaint",
        "escalate",
        "unsupported",
    ]
    escalation_required: bool
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str
    draft_reply: str
    human_review_required: Literal[True]
    customer_outcome: None = None


class TriageOutputWithAnalysis(TriageOutput):
    analysis: str


class SummarizationOutput(StrictModel):
    document_status: DocumentStatus
    title: EvidenceField
    version: EvidenceField
    effective_date: EvidenceField
    purpose: EvidenceField
    required_steps: EvidenceField
    exceptions: EvidenceField

    def evidence_fields(self) -> dict[str, EvidenceField]:
        return {
            "title": self.title,
            "version": self.version,
            "effective_date": self.effective_date,
            "purpose": self.purpose,
            "required_steps": self.required_steps,
            "exceptions": self.exceptions,
        }


class PolicyExtraction(StrictModel):
    document_status: DocumentStatus
    policy_name: EvidenceField
    version: EvidenceField
    effective_date: EvidenceField
    jurisdictions: EvidenceField
    beneficial_ownership_threshold: EvidenceField
    review_frequency: EvidenceField
    required_documents: EvidenceField

    def evidence_fields(self) -> dict[str, EvidenceField]:
        return {
            "policy_name": self.policy_name,
            "version": self.version,
            "effective_date": self.effective_date,
            "jurisdictions": self.jurisdictions,
            "beneficial_ownership_threshold": self.beneficial_ownership_threshold,
            "review_frequency": self.review_frequency,
            "required_documents": self.required_documents,
        }


OUTPUT_SCHEMAS: dict[TaskName, type[StrictModel]] = {
    "triage": TriageOutput,
    "summarization": SummarizationOutput,
    "extraction": PolicyExtraction,
}


def schema_description(model: type[BaseModel]) -> str:
    """Text description of a Pydantic model, derived from the model itself."""
    lines = [
        f"Return one filled JSON object of type {model.__name__}.",
        "Do not return JSON Schema. Do not emit $defs, anyOf, properties, or additionalProperties.",
    ]
    if model.model_config.get("extra") == "forbid":
        lines.append("Do not add keys that are not listed below.")
    if _uses_model(model, EvidenceField):
        lines.append(
            'Every EvidenceField must include "value", "status", and "citation". '
            'When status is "absent" or "ambiguous", still set "value": null. Never omit "value".'
        )
    lines.append("Fields:")
    lines.extend(_describe_fields(model, indent=0))
    return "\n".join(lines)


def _uses_model(model: type[BaseModel], target: type[BaseModel]) -> bool:
    if model is target:
        return True
    for field in model.model_fields.values():
        nested = _as_model_type(field.annotation)
        if nested is not None and _uses_model(nested, target):
            return True
    return False


def _describe_fields(model: type[BaseModel], indent: int) -> list[str]:
    pad = "  " * indent
    lines: list[str] = []
    for name, field in model.model_fields.items():
        annotation = field.annotation
        nested = _as_model_type(annotation)
        if nested is not None:
            lines.append(f"{pad}- {name}: {nested.__name__} object")
            lines.extend(_describe_fields(nested, indent + 1))
        else:
            lines.append(f"{pad}- {name}: {_type_label(annotation)}")
    return lines


def _as_model_type(annotation: object) -> type[BaseModel] | None:
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return annotation
    return None


def _type_label(annotation: object) -> str:
    origin = get_origin(annotation)
    args = get_args(annotation)
    if origin is Literal:
        return " | ".join(repr(arg) for arg in args)
    if origin in (Union, types.UnionType):
        return " | ".join(_type_label(arg) for arg in args)
    if origin is list:
        inner = _type_label(args[0]) if args else "any"
        return f"list[{inner}]"
    if annotation is type(None):
        return "null"
    if isinstance(annotation, type):
        return annotation.__name__
    return str(annotation)

