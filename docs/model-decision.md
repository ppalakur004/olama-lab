# Model Decision Record

Run ID: `day5-local-01`

Models: mistral, qwen.

Qwen rows used the same prompt files as Mistral (`transfer` = unadapted).

## Summarization

| Model | Prompt | Valid | Recall | Missed | Citations | Doc status | Invented | Avoided extra | PII | Repairs | Failures | In / out tokens | Median / max latency |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| mistral | `summarize.v1` | 12/12 | 59/60 | 1/60 | 17/63 | 8/12 | 4/12 | 8/12 | 0/12 | 1/12 | 0 | 13857 / 3793 | 12916 / 16346 ms |
| qwen | `summarize.v1 transfer` | 11/12 | 55/55 | 0/55 | 0/56 | 11/11 | 1/11 | 10/11 | 0/11 | 1/12 | 1 | 11838 / 11482 | 31512 / 89785 ms |

- **Decision:** summarization → mistral → `summarize.v1`
- **Why:** all 12 valid vs Qwen 11/12 (truncated), citations were 17/63 vs 0/56, and Mistral was much faster. Qwen recovered 55/55 required fields among its validated outputs, so the decision depends on validity, citations, and latency rather than recall alone.
- **Rejected:** qwen / `summarize.v1 transfer`
- **Reopen if:** citations must beat 17/63, or a Qwen-specific summarize prompt is measured.

## Extraction

| Model | Prompt | Valid | Recall | Missed | Citations | Doc status | Invented | Avoided extra | PII | Version pick | Repairs | Failures | In / out tokens | Median / max latency |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| mistral | `extract.v2` | 12/12 | 71/72 | 1/72 | 49/76 | 9/12 | 5/12 | 7/12 | 0/12 | 0/1 | 0/12 | 0 | 17807 / 4531 | 17003.5 / 19710 ms |
| qwen | `extract.v2 transfer` | 11/12 | 66/66 | 0/66 | 14/68 | 10/11 | 2/11 | 9/11 | 0/11 | 1/1 | 2/12 | 1 | 17936 / 17820 | 47091 / 94051 ms |

- **Decision:** extraction → mistral → `extract.v2`
- **Why:** all 12 valid vs Qwen 11/12 (truncated), citations were 49/76 vs 14/68, and Mistral was much faster. Qwen recovered 66/66 required fields among validated outputs, but its final failure remains operationally significant. Citations are still a gap.
- **Rejected:** qwen / `extract.v2 transfer`
- **Reopen if:** a Qwen extract prompt stays valid with better citations and no truncation, or citations must beat 49/76.

## Triage

| Model | Prompt | Valid | Queue | Escalation | Missed esc. | Extra esc. | Human boundary | PII | Repairs | Failures | In / out tokens | Median / max latency |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| mistral | `triage.v1` | 12/12 | 10/12 | 11/12 | 1/12 | 0/12 | 12/12 | 0/12 | 1/12 | 0 | 10849 / 1331 | 4295 / 4788 ms |
| qwen | `triage.v1 transfer` | 12/12 | 12/12 | 12/12 | 0/12 | 0/12 | 12/12 | 0/12 | 0/12 | 0 | 8479 / 3833 | 13324.5 / 20232 ms |

Human-boundary passed on both models. No `draft_reply` promised a refund, approved/denied a claim, or said the case was done.

- **Decision:** triage → qwen → `triage.v1` (recorded as `triage.v1 transfer`)
- **Why:** Qwen queue 12/12 and escalation 12/12. Mistral 10/12 queue, 11/12 escalation. Both 12/12 on human-boundary and 0/12 PII. Qwen is slower; routing is why it wins.
- **Rejected:** mistral / `triage.v1` (faster, worse routing)
- **Reopen if:** replies must stay near ~4s, or a new Mistral triage prompt hits 12/12 queue.

## Limitations

- Each task has only 12 cases. Counts are directional evidence, not production-scale estimates, and a one-case difference does not prove universal model superiority.
- Qwen rows are prompt-transfer / unadapted. No Qwen-specific prompt was measured; adapted prompts would compare model + prompt configurations.
- Untested model/prompt combinations remain untested and should not be inferred from these rows.
- Failed structured outputs remain visible in the 12-case population but are excluded from deterministic field-metric denominators.
- Local latency depends on this machine and its load, so different deployment hardware can reopen the decisions.
- No production-reliability claim is made. The provider/API charge for these local Ollama calls was `$0.00`.
