from __future__ import annotations

import json

from pydantic import BaseModel, ValidationError

from promptlab.adapters.base import CompletionRequest, CompletionResult, ModelAdapter


def complete_structured[T: BaseModel](
    adapter: ModelAdapter,
    request: CompletionRequest,
    schema: type[T],
    run_id: str,
    max_repairs: int = 1,
) -> T:
    """Return a schema-validated completion with a bounded semantic repair loop.

    Transport retry remains inside the adapter.
    Schema/content repair belongs here.

    On validation failure, send the validation error text back to the model and
    instruct it to correct only what the error concerns. Do not perform more
    than max_repairs semantic repair attempts.
    """

    result = adapter.complete(request, run_id)
    parsed, error = _parse_and_validate(schema, result)
    if parsed is not None:
        return parsed

    current = request
    last_error = error or "Response did not match the schema."
    for _ in range(max_repairs):
        current = current.model_copy(
            update={"user_content": _repair_user_content(request, last_error)}
        )
        result = adapter.complete(current, run_id)
        parsed, error = _parse_and_validate(schema, result)
        if parsed is not None:
            return parsed
        last_error = error or last_error

    raise ValueError(last_error)


def _repair_user_content(original: CompletionRequest, error_text: str) -> str:
    return (
        f"{original.user_content}\n\n"
        "The previous response failed validation.\n"
        f"Validation error:\n{error_text}\n"
        "Correct only what the validation error concerns. "
        "Every EvidenceField must include value (use null if absent), status, and citation. "
        "Do not add keys that are not in the schema. "
        "Return only one filled JSON object. Do not return JSON Schema."
    )


def _parse_and_validate[T: BaseModel](
    schema: type[T],
    result: CompletionResult,
) -> tuple[T | None, str | None]:
    if not result.text or not result.text.strip():
        return None, "Validation error: empty response text."
    try:
        payload = _load_json(result.text)
        return schema.model_validate(payload), None
    except (json.JSONDecodeError, ValidationError, TypeError, ValueError) as exc:
        return None, f"Validation error: {exc}"


def _load_json(text: str) -> object:
    raw = text.strip()
    if raw.startswith("```"):
        lines = raw.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        raw = "\n".join(lines).strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise
        return json.loads(raw[start : end + 1])
