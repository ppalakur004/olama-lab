from decimal import Decimal
from pathlib import Path

from promptlab.records import OutputRecord, ScoreRecord, UsageRecord
from promptlab.report import write_reports


def test_report_is_generated_from_records(tmp_path: Path) -> None:
    usage = [
        UsageRecord(
            run_id="demo",
            task="triage",
            case_id="T01",
            model_name="mistral",
            model_id="mistral:7b",
            prompt_version="triage-mistral-v1",
            attempt=1,
            kind="primary",
            status="success",
            prompt_tokens=100,
            completion_tokens=25,
            latency_ms=125.0,
            cost_usd=Decimal("0"),
        )
    ]
    outputs = [
        OutputRecord(
            run_id="demo",
            task="triage",
            case_id="T01",
            model_name="mistral",
            model_id="mistral:7b",
            prompt_version="triage-mistral-v1",
            succeeded=True,
            repairs=0,
            output={"queue": "card_dispute"},
        )
    ]
    scores = [
        ScoreRecord(
            run_id="demo",
            task="triage",
            case_id="T01",
            model_name="mistral",
            prompt_version="triage-mistral-v1",
            scorer_version="2.0.0",
            metric="queue_accuracy",
            numerator=1,
            denominator=1,
        )
    ]
    report = tmp_path / "comparison.md"
    decision = tmp_path / "model-decision.md"
    write_reports(
        run_id="demo",
        models=["mistral"],
        usage=usage,
        outputs=outputs,
        scores=scores,
        report_path=report,
        decision_path=decision,
    )
    assert "1/1" in report.read_text(encoding="utf-8")
    assert "triage-mistral-v1" in report.read_text(encoding="utf-8")
    assert "Call observations" in report.read_text(encoding="utf-8")
    assert "production-reliability claim" in report.read_text(encoding="utf-8")
    assert "mistral" in decision.read_text(encoding="utf-8")


def test_report_preserves_existing_decision_and_excludes_failed_output_scores(
    tmp_path: Path,
) -> None:
    outputs = [
        OutputRecord(
            run_id="demo",
            task="extraction",
            case_id="E01",
            model_name="qwen",
            model_id="qwen3:8b",
            prompt_version="extract.v2 transfer",
            succeeded=True,
            repairs=0,
            output={"document_status": "valid"},
        ),
        OutputRecord(
            run_id="demo",
            task="extraction",
            case_id="E02",
            model_name="qwen",
            model_id="qwen3:8b",
            prompt_version="extract.v2 transfer",
            succeeded=False,
            repairs=1,
            output=None,
            error="Validation error",
        ),
    ]
    scores = [
        ScoreRecord(
            run_id="demo",
            task="extraction",
            case_id="E01",
            model_name="qwen",
            prompt_version="extract.v2 transfer",
            scorer_version="day5-v2",
            metric="required_evidence_recall",
            numerator=6,
            denominator=6,
        )
    ]
    report = tmp_path / "comparison.md"
    decision = tmp_path / "model-decision.md"
    decision.write_text("hand-authored decision\n", encoding="utf-8")

    write_reports(
        run_id="demo",
        models=["qwen"],
        usage=[],
        outputs=outputs,
        scores=scores,
        report_path=report,
        decision_path=decision,
    )

    text = report.read_text(encoding="utf-8")
    assert "1/2" in text
    assert "required_evidence_recall: 6/6" in text
    assert decision.read_text(encoding="utf-8") == "hand-authored decision\n"
