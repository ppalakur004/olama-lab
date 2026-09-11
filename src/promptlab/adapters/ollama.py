"""Ollama adapter: one class, model chosen by configured model_id."""

from __future__ import annotations

import random
import time
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import httpx

from promptlab.adapters.base import CompletionRequest, CompletionResult
from promptlab.config import Settings
from promptlab.errors import (
    PermanentProviderError,
    TransientProviderError,
    TruncatedResponseError,
)
from promptlab.usage import CallRecord, append_record, compute_cost

MAX_ATTEMPTS = 3
TRANSIENT_STATUS_CODES = frozenset({408, 429, 500, 502, 503, 504})


class OllamaAdapter:
    provider = "ollama"

    def __init__(self, model_id: str) -> None:
        self.model_id = model_id
        self._settings = Settings.from_env()

    def complete(self, request: CompletionRequest, run_id: str) -> CompletionResult:
        records: list[CallRecord] = []
        last_error: str | None = None

        for attempt in range(1, MAX_ATTEMPTS + 1):
            record, kind, text = self._one_attempt(request, run_id, attempt)
            append_record(record, run_id)
            records.append(record)
            last_error = record.error_type

            if kind == "success":
                return CompletionResult(
                    succeeded=True,
                    text=text,
                    error_type=None,
                    records=records,
                )
            if kind != "transient" or attempt == MAX_ATTEMPTS:
                return CompletionResult(
                    succeeded=False,
                    text=text if kind == "truncated" else None,
                    error_type=last_error,
                    records=records,
                )
            time.sleep(self._backoff_seconds(attempt))

        return CompletionResult(
            succeeded=False,
            text=None,
            error_type=last_error,
            records=records,
        )

    def _one_attempt(
        self,
        request: CompletionRequest,
        run_id: str,
        attempt: int,
    ) -> tuple[CallRecord, str, str | None]:
        started = time.perf_counter()
        payload: dict[str, Any] = {}
        kind = "success"
        error_type: str | None = None
        text: str | None = None
        stop_reason: str | None = None
        input_tokens = 0
        output_tokens = 0

        try:
            response = httpx.post(
                f"{self._settings.ollama_base_url}/api/generate",
                json={
                    "model": self.model_id,
                    "prompt": f"{request.system}\n\n{request.user_content}",
                    "stream": False,
                    "options": {
                        "temperature": request.temperature,
                        "num_predict": request.max_output_tokens,
                    },
                },
                timeout=180.0,
            )
            latency_ms = int(round((time.perf_counter() - started) * 1000))
            status = response.status_code
            if status in TRANSIENT_STATUS_CODES or status >= 500:
                kind = "transient"
                error_type = TransientProviderError.__name__
            elif status >= 400:
                kind = "permanent"
                error_type = PermanentProviderError.__name__
            else:
                raw = response.json()
                if isinstance(raw, dict):
                    payload = raw
                text = _response_text(payload)
                input_tokens = _as_int(payload.get("prompt_eval_count"))
                output_tokens = _as_int(payload.get("eval_count"))
                stop_reason = _as_optional_str(payload.get("done_reason"))
                if stop_reason == "length":
                    kind = "truncated"
                    error_type = TruncatedResponseError.__name__
        except (httpx.TimeoutException, httpx.NetworkError, httpx.TransportError):
            latency_ms = int(round((time.perf_counter() - started) * 1000))
            kind = "transient"
            error_type = TransientProviderError.__name__

        if error_type is not None and kind != "truncated":
            text = None

        record = CallRecord(
            record_id=str(uuid4()),
            run_id=run_id,
            timestamp=datetime.now(UTC),
            provider="ollama",
            model_id=self.model_id,
            task=request.task,
            case_id=request.case_id,
            prompt_id=request.prompt_id,
            prompt_version=request.prompt_version,
            attempt=attempt,
            temperature=request.temperature,
            max_output_tokens=request.max_output_tokens,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cached_input_tokens=None,
            latency_ms=latency_ms,
            cost_usd=compute_cost(self.model_id, input_tokens, output_tokens),
            stop_reason=stop_reason,
            error_type=error_type,
            response_text=text,
        )
        return record, kind, text

    @staticmethod
    def _backoff_seconds(failed_attempt: int) -> float:
        return float((2 ** (failed_attempt - 1)) * 0.25 + random.uniform(0.0, 0.25))


def _as_int(value: object) -> int:
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    return 0


def _as_optional_str(value: object) -> str | None:
    if isinstance(value, str):
        return value
    return None


def _response_text(payload: dict[str, Any]) -> str | None:
    message = payload.get("message")
    if isinstance(message, dict):
        content = message.get("content")
        if isinstance(content, str):
            return content
    response = payload.get("response")
    if isinstance(response, str):
        return response
    return None
