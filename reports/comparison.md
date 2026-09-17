# Model Comparison

Run ID: `day5-local-nothink-01`

Counts are reported with their denominators. Latency uses median and maximum rather than mean.

## Extraction

| Model | Prompt | Valid outputs | Metrics | Input tokens | Output tokens | Median case latency | Max case latency | Latency n | Repairs | Retries | Final failures |
| --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| mistral | extract.v2 | 12/12 | citation_correctness: 49/76<br>document_status: 9/12<br>invented_unsupported: 5/12 ↓<br>missed_required_evidence: 1/72 ↓<br>pii_leakage: 0/12 ↓<br>required_evidence_recall: 71/72<br>unsupported_field_avoidance: 7/12<br>version_selection_accuracy: 0/1 | 17807 | 4531 | 17073 ms | 20413 ms | 12 | 0/12 | 0 | 0 |
| qwen | extract.v2 transfer | 12/12 | citation_correctness: 73/73<br>document_status: 10/12<br>invented_unsupported: 2/12 ↓<br>missed_required_evidence: 1/72 ↓<br>pii_leakage: 0/12 ↓<br>required_evidence_recall: 71/72<br>unsupported_field_avoidance: 10/12<br>version_selection_accuracy: 1/1 | 15335 | 3330 | 13986 ms | 17710 ms | 12 | 0/12 | 0 | 0 |

## Summarization

| Model | Prompt | Valid outputs | Metrics | Input tokens | Output tokens | Median case latency | Max case latency | Latency n | Repairs | Retries | Final failures |
| --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| mistral | summarize.v1 | 12/12 | citation_correctness: 17/63<br>document_status: 8/12<br>invented_unsupported: 4/12 ↓<br>missed_required_evidence: 1/60 ↓<br>pii_leakage: 0/12 ↓<br>required_evidence_recall: 59/60<br>unsupported_field_avoidance: 8/12 | 13857 | 3793 | 13084 ms | 24277 ms | 12 | 1/12 | 0 | 0 |
| qwen | summarize.v1 transfer | 12/12 | citation_correctness: 63/63<br>document_status: 11/12<br>invented_unsupported: 3/12 ↓<br>missed_required_evidence: 0/60 ↓<br>pii_leakage: 0/12 ↓<br>required_evidence_recall: 60/60<br>unsupported_field_avoidance: 9/12 | 10947 | 2980 | 12284.5 ms | 16148 ms | 12 | 0/12 | 0 | 0 |

## Triage

| Model | Prompt | Valid outputs | Metrics | Input tokens | Output tokens | Median case latency | Max case latency | Latency n | Repairs | Retries | Final failures |
| --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| mistral | triage.v1 | 12/12 | escalation: 11/12<br>human_boundary_compliance: 12/12<br>missed_escalation: 1/12 ↓<br>pii_leakage: 0/12 ↓<br>queue: 10/12<br>unnecessary_escalation: 0/12 ↓ | 10849 | 1331 | 4709 ms | 9408 ms | 12 | 1/12 | 0 | 0 |
| qwen | triage.v1 transfer | 12/12 | escalation: 12/12<br>human_boundary_compliance: 12/12<br>missed_escalation: 0/12 ↓<br>pii_leakage: 0/12 ↓<br>queue: 12/12<br>unnecessary_escalation: 0/12 ↓ | 8551 | 852 | 3842 ms | 6304 ms | 12 | 0/12 | 0 | 0 |

## Limits

- Each task uses a fixed set of 12 gold cases. Report counts; do not treat one-case gaps as production estimates or proof of universal model superiority.
- A row measures that model together with the prompt version shown. Rows ending in `transfer` are prompt-transfer / unadapted: the same markdown files as Mistral, not a Qwen-specific rewrite.
- Adapted-prompt rows compare model + prompt configurations rather than models alone. Untested combinations are identified as untested.
- Untested: Qwen-specific adapted prompts for summarization, extraction, and triage.
- Failed structured outputs remain visible in the 12-case experiment and are excluded from deterministic field-metric denominators.
- Measured on local Ollama in this environment (`mistral:7b`, `qwen3:8b`), temperature `0.0`; Qwen used `think=false`. Case latency sums all recorded attempt latencies for an evaluation. Local latency depends on the current machine and load.
- These directional results do not make a production-reliability claim.
- Local Ollama provider/API charge is `$0.00`; token usage and latency still represent real operational work.
