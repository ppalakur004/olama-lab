# Model Comparison

Run ID: `day5-local-01`

Counts are reported with their denominators. Latency uses median and maximum rather than mean.

## Extraction

| Model | Prompt | Valid outputs | Metrics | Input tokens | Output tokens | Median latency | Max latency | Call observations | Repairs | Retries | Final failures |
| --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| mistral | extract.v2 | 12/12 | citation_correctness: 49/76<br>document_status: 9/12<br>invented_unsupported: 5/12 ↓<br>missed_required_evidence: 1/72 ↓<br>pii_leakage: 0/12 ↓<br>required_evidence_recall: 71/72<br>unsupported_field_avoidance: 7/12<br>version_selection_accuracy: 0/1 | 17807 | 4531 | 17003.5 ms | 19710 ms | 12 | 0/12 | 0 | 0 |
| qwen | extract.v2 transfer | 11/12 | citation_correctness: 14/68<br>document_status: 10/11<br>invented_unsupported: 2/11 ↓<br>missed_required_evidence: 0/66 ↓<br>pii_leakage: 0/11 ↓<br>required_evidence_recall: 66/66<br>unsupported_field_avoidance: 9/11<br>version_selection_accuracy: 1/1 | 17936 | 17820 | 47091 ms | 94051 ms | 14 | 2/12 | 0 | 1 |

## Summarization

| Model | Prompt | Valid outputs | Metrics | Input tokens | Output tokens | Median latency | Max latency | Call observations | Repairs | Retries | Final failures |
| --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| mistral | summarize.v1 | 12/12 | citation_correctness: 17/63<br>document_status: 8/12<br>invented_unsupported: 4/12 ↓<br>missed_required_evidence: 1/60 ↓<br>pii_leakage: 0/12 ↓<br>required_evidence_recall: 59/60<br>unsupported_field_avoidance: 8/12 | 13857 | 3793 | 12916 ms | 16346 ms | 13 | 1/12 | 0 | 0 |
| qwen | summarize.v1 transfer | 11/12 | citation_correctness: 0/56<br>document_status: 11/11<br>invented_unsupported: 1/11 ↓<br>missed_required_evidence: 0/55 ↓<br>pii_leakage: 0/11 ↓<br>required_evidence_recall: 55/55<br>unsupported_field_avoidance: 10/11 | 11838 | 11482 | 31512 ms | 89785 ms | 13 | 1/12 | 0 | 1 |

## Triage

| Model | Prompt | Valid outputs | Metrics | Input tokens | Output tokens | Median latency | Max latency | Call observations | Repairs | Retries | Final failures |
| --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| mistral | triage.v1 | 12/12 | escalation: 11/12<br>human_boundary_compliance: 12/12<br>missed_escalation: 1/12 ↓<br>pii_leakage: 0/12 ↓<br>queue: 10/12<br>unnecessary_escalation: 0/12 ↓ | 10849 | 1331 | 4295 ms | 4788 ms | 13 | 1/12 | 0 | 0 |
| qwen | triage.v1 transfer | 12/12 | escalation: 12/12<br>human_boundary_compliance: 12/12<br>missed_escalation: 0/12 ↓<br>pii_leakage: 0/12 ↓<br>queue: 12/12<br>unnecessary_escalation: 0/12 ↓ | 8479 | 3833 | 13324.5 ms | 20232 ms | 12 | 0/12 | 0 | 0 |

## Limits

- Each task uses a fixed set of 12 gold cases. Report counts; do not treat one-case gaps as production estimates or proof of universal model superiority.
- A row measures that model together with the prompt version shown. Rows ending in `transfer` are prompt-transfer / unadapted: the same markdown files as Mistral, not a Qwen-specific rewrite.
- Adapted-prompt rows compare model + prompt configurations rather than models alone. Untested combinations are identified as untested.
- Untested: Qwen-specific adapted prompts for summarization, extraction, and triage.
- Failed structured outputs remain visible in the 12-case experiment and are excluded from deterministic field-metric denominators.
- Measured on local Ollama in this environment (`mistral:7b`, `qwen3:8b`), temperature `0.0`. Local latency depends on the current machine and load.
- These directional results do not make a production-reliability claim.
- Local Ollama provider/API charge is `$0.00`; token usage and latency still represent real operational work.
