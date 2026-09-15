"""Day 5 harness: three tasks, two configured local models, one run_id."""

from __future__ import annotations

import argparse
import re
import shutil
from collections import defaultdict
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Literal, cast

from promptlab.adapters.base import CompletionRequest
from promptlab.adapters.ollama import OllamaAdapter
from promptlab.config import PROJECT_ROOT, ModelConfig, Settings
from promptlab.corpus import GoldLabel, load_cases, validate_corpus
from promptlab.prompts import build_prompt, prompt_spec, prompt_version
from promptlab.records import OutputRecord, ScoreRecord, UsageRecord, append_record
from promptlab.report import write_reports
from promptlab.rules import VersionCandidate, select_current_version
from promptlab.schemas import (
    OUTPUT_SCHEMAS,
    PolicyExtraction,
    StrictModel,
    SummarizationOutput,
    TaskName,
)
from promptlab.scoring import SCORER_VERSION, failure_scores, score_output
from promptlab.structured import complete_structured
from promptlab.usage import CallRecord

RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")
TEMPERATURE = 0.0
MAX_OUTPUT_TOKENS: dict[TaskName, int] = {
    "triage": 1024,
    "summarization": 2048,
    "extraction": 2048,
}
AttemptKind = Literal["primary", "transport_retry", "repair", "repair_retry"]


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the local two-model prompt comparison")
    parser.add_argument("--run-id", help="Stable identifier for this run")
    parser.add_argument("--task", choices=["triage", "summarization", "extraction"])
    parser.add_argument("--model", choices=["mistral", "qwen"])
    parser.add_argument("--limit", type=int, help="Limit cases per task for a smoke run")
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate configuration and corpus without calling Ollama",
    )
    return parser


def _call_log_path(run_id: str) -> Path:
    return Path("runs") / f"{run_id}.jsonl"


def _load_call_records(run_id: str) -> list[CallRecord]:
    path = _call_log_path(run_id)
    if not path.exists():
        return []
    records: list[CallRecord] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            records.append(CallRecord.model_validate_json(line))
    return records


def _attempt_kinds(records: list[CallRecord]) -> list[AttemptKind]:
    kinds: list[AttemptKind] = []
    completes = 0
    for record in records:
        if record.attempt == 1:
            completes += 1
            kinds.append("primary" if completes == 1 else "repair")
        elif completes <= 1:
            kinds.append("transport_retry")
        else:
            kinds.append("repair_retry")
    return kinds


def _usage_from_call(
    *,
    run_id: str,
    task: TaskName,
    case_id: str,
    model: ModelConfig,
    version: str,
    record: CallRecord,
    kind: AttemptKind,
) -> UsageRecord:
    status: Literal["success", "schema_invalid", "transport_error"] = (
        "transport_error" if record.error_type else "success"
    )
    return UsageRecord(
        run_id=run_id,
        task=task,
        case_id=case_id,
        model_name=model.logical_name,
        model_id=model.model_id,
        prompt_version=version,
        attempt=record.attempt,
        kind=kind,
        status=status,
        prompt_tokens=record.input_tokens,
        completion_tokens=record.output_tokens,
        latency_ms=float(record.latency_ms),
        cost_usd=Decimal(str(record.cost_usd)),
        error=record.error_type,
    )


def _version_fields(output: StrictModel) -> tuple[str, str] | None:
    if isinstance(output, SummarizationOutput | PolicyExtraction):
        version = output.version
        effective = output.effective_date
        if (
            version.status == "present"
            and effective.status == "present"
            and isinstance(version.value, str)
            and isinstance(effective.value, str)
        ):
            return version.value, effective.value
    return None


def _add_version_scores(
    *,
    run_id: str,
    task: TaskName,
    model_name: str,
    labels: list[GoldLabel],
    outputs: dict[str, StrictModel],
    scores_path: Path,
    all_scores: list[ScoreRecord],
) -> None:
    grouped: dict[str, list[GoldLabel]] = defaultdict(list)
    for label in labels:
        if label.version_group:
            grouped[label.version_group].append(label)

    for group_name, group_labels in grouped.items():
        if len(group_labels) < 2:
            continue
        expected = next(
            (
                label.expected_current_case_id
                for label in group_labels
                if label.expected_current_case_id
            ),
            None,
        )
        as_of_raw = next((label.as_of for label in group_labels if label.as_of), None)
        if expected is None or as_of_raw is None:
            continue
        candidates: list[VersionCandidate] = []
        prompt_versions: set[str] = set()
        for label in group_labels:
            output = outputs.get(label.id)
            if output is None:
                continue
            extracted = _version_fields(output)
            if extracted is None:
                continue
            version, effective_raw = extracted
            try:
                effective = date.fromisoformat(effective_raw)
            except ValueError:
                continue
            candidates.append(
                VersionCandidate(case_id=label.id, version=version, effective_date=effective)
            )
            prompt_versions.add(prompt_version(task, model_name))
        selected = select_current_version(candidates, date.fromisoformat(as_of_raw))
        record = ScoreRecord(
            run_id=run_id,
            task=task,
            case_id=f"version:{group_name}",
            model_name=model_name,
            prompt_version=",".join(sorted(prompt_versions)) or prompt_version(task, model_name),
            scorer_version=SCORER_VERSION,
            metric="version_selection_accuracy",
            numerator=int(selected is not None and selected.case_id == expected),
            denominator=1,
            detail=f"expected={expected}; selected={selected.case_id if selected else 'none'}",
        )
        append_record(scores_path, record)
        all_scores.append(record)


def _copy_docs(run_id: str, scores_path: Path) -> None:
    docs = PROJECT_ROOT / "docs"
    docs.mkdir(parents=True, exist_ok=True)
    call_log = _call_log_path(run_id)
    if call_log.exists():
        shutil.copyfile(call_log, docs / "day5-run.jsonl")
    if scores_path.exists():
        shutil.copyfile(scores_path, docs / "day5-scores.jsonl")


def main() -> None:
    args = _parser().parse_args()
    counts = validate_corpus()
    if args.validate_only:
        print("Corpus valid: " + ", ".join(f"{task}={count}" for task, count in counts.items()))
        return

    run_id = cast(str | None, args.run_id)
    if run_id is None or not RUN_ID_PATTERN.fullmatch(run_id):
        raise SystemExit("--run-id is required and must use letters, numbers, '.', '_' or '-'")
    limit = cast(int | None, args.limit)
    if limit is not None and limit < 1:
        raise SystemExit("--limit must be at least 1")

    selected_tasks: list[TaskName]
    if args.task:
        selected_tasks = [cast(TaskName, args.task)]
    else:
        selected_tasks = ["triage", "summarization", "extraction"]

    settings = Settings.from_env()
    selected_models = [cast(str, args.model)] if args.model else list(settings.models)
    run_dir = PROJECT_ROOT / "runs" / run_id
    if run_dir.exists():
        raise SystemExit(f"Run directory already exists: {run_dir}")
    run_dir.mkdir(parents=True)
    usage_path = run_dir / "usage.jsonl"
    outputs_path = run_dir / "outputs.jsonl"
    scores_path = run_dir / "scores.jsonl"

    all_usage: list[UsageRecord] = []
    all_outputs: list[OutputRecord] = []
    all_scores: list[ScoreRecord] = []
    total_cost = Decimal("0")
    validated_by_task_model: dict[tuple[TaskName, str], dict[str, StrictModel]] = defaultdict(dict)
    labels_by_task: dict[TaskName, list[GoldLabel]] = defaultdict(list)
    adapters = {
        name: OllamaAdapter(model_id=settings.models[name].model_id) for name in selected_models
    }

    for task in selected_tasks:
        pairs = load_cases(task)
        if limit is not None:
            pairs = pairs[:limit]
        labels_by_task[task] = [gold for _case, gold in pairs]
        prompt_id, file_version = prompt_spec(task)
        schema = OUTPUT_SCHEMAS[task]
        for model_name in selected_models:
            model = settings.models[model_name]
            adapter = adapters[model_name]
            version = prompt_version(task, model_name)
            for case, gold in pairs:
                if total_cost >= settings.per_run_cap_usd:
                    raise SystemExit(
                        f"Per-run cost cap reached before {task}/{model_name}/{case.id}"
                    )
                built = build_prompt(task, model_name, case.document_text)
                request = CompletionRequest(
                    task=task,
                    case_id=case.id,
                    prompt_id=prompt_id,
                    prompt_version=file_version,
                    system=built.system,
                    user_content=built.user_content,
                    temperature=TEMPERATURE,
                    max_output_tokens=MAX_OUTPUT_TOKENS[task],
                )
                before = len(_load_call_records(run_id))
                parsed: StrictModel | None = None
                error_text: str | None = None
                try:
                    parsed = complete_structured(adapter, request, schema, run_id)
                except ValueError as exc:
                    error_text = str(exc)
                new_records = _load_call_records(run_id)[before:]
                kinds = _attempt_kinds(new_records)
                for record, kind in zip(new_records, kinds, strict=True):
                    usage_record = _usage_from_call(
                        run_id=run_id,
                        task=task,
                        case_id=case.id,
                        model=model,
                        version=version,
                        record=record,
                        kind=kind,
                    )
                    append_record(usage_path, usage_record)
                    all_usage.append(usage_record)
                    total_cost += usage_record.cost_usd
                repairs = sum(1 for kind in kinds if kind == "repair")
                if parsed is not None:
                    output_record = OutputRecord(
                        run_id=run_id,
                        task=task,
                        case_id=case.id,
                        model_name=model_name,
                        model_id=model.model_id,
                        prompt_version=version,
                        succeeded=True,
                        repairs=repairs,
                        output=parsed.model_dump(mode="json"),
                    )
                    validated_by_task_model[(task, model_name)][case.id] = parsed
                    case_scores = score_output(
                        run_id=run_id,
                        task=task,
                        case_id=case.id,
                        model_name=model_name,
                        prompt_version=version,
                        output=parsed,
                        gold=gold,
                        source=case.document_text,
                    )
                else:
                    output_record = OutputRecord(
                        run_id=run_id,
                        task=task,
                        case_id=case.id,
                        model_name=model_name,
                        model_id=model.model_id,
                        prompt_version=version,
                        succeeded=False,
                        repairs=repairs,
                        output=None,
                        error=error_text,
                    )
                    case_scores = failure_scores(
                        run_id=run_id,
                        task=task,
                        case_id=case.id,
                        model_name=model_name,
                        prompt_version=version,
                        gold=gold,
                    )
                append_record(outputs_path, output_record)
                all_outputs.append(output_record)
                for score in case_scores:
                    append_record(scores_path, score)
                    all_scores.append(score)
                print(
                    f"{task:13} {model_name:8} {case.id:5} "
                    f"{'ok' if output_record.succeeded else 'failed'}"
                )

    for task in selected_tasks:
        if task == "triage":
            continue
        for model_name in selected_models:
            _add_version_scores(
                run_id=run_id,
                task=task,
                model_name=model_name,
                labels=labels_by_task[task],
                outputs=validated_by_task_model[(task, model_name)],
                scores_path=scores_path,
                all_scores=all_scores,
            )

    write_reports(
        run_id=run_id,
        models=selected_models,
        usage=all_usage,
        outputs=all_outputs,
        scores=all_scores,
        report_path=PROJECT_ROOT / "reports" / "comparison.md",
        decision_path=PROJECT_ROOT / "docs" / "model-decision.md",
    )
    _copy_docs(run_id, scores_path)
    print(f"Report: {PROJECT_ROOT / 'reports' / 'comparison.md'}")
    print(f"Recorded provider cost: ${total_cost}")


if __name__ == "__main__":
    main()
