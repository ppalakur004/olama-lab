# Model Decision Record

Final run ID: `day5-local-nothink-01`

Models: `mistral:7b` and `qwen3:8b`. Temperature was `0.0`. Qwen thinking was explicitly disabled with `think=false`.

Qwen used the same prompt files as Mistral (`transfer` = prompt-transfer / unadapted). Earlier run `day5-local-01` used the runtime's default Qwen thinking behavior and is not mixed into this final comparison.

## Summarization

| Model | Prompt | Valid | Recall | Missed | Citations | Doc status | Invented | Avoided extra | PII | Repairs | Failures | In / out tokens | Median / max case latency |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| mistral | `summarize.v1` | 12/12 | 59/60 | 1/60 | 17/63 | 8/12 | 4/12 | 8/12 | 0/12 | 1/12 | 0 | 13857 / 3793 | 13084 / 24277 ms |
| qwen | `summarize.v1 transfer` | 12/12 | 60/60 | 0/60 | 63/63 | 11/12 | 3/12 | 9/12 | 0/12 | 0/12 | 0 | 10947 / 2980 | 12284.5 / 16148 ms |

- **Decision:** summarization → qwen → `summarize.v1 transfer`
- **Why:** Qwen validated 12/12, recovered 60/60 required fields, produced 63/63 correct citations, used fewer tokens, required no repairs, and had lower median and maximum case latency.
- **Rejected:** mistral / `summarize.v1` because it missed one required field, had 17/63 correct citations, and required one repair.
- **Reopen if:** the prompt or model tag changes, a larger case set materially changes citation or validation behavior, or Qwen thinking is enabled again.

## Extraction

| Model | Prompt | Valid | Recall | Missed | Citations | Doc status | Invented | Avoided extra | PII | Version pick | Repairs | Failures | In / out tokens | Median / max case latency |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| mistral | `extract.v2` | 12/12 | 71/72 | 1/72 | 49/76 | 9/12 | 5/12 | 7/12 | 0/12 | 0/1 | 0/12 | 0 | 17807 / 4531 | 17073 / 20413 ms |
| qwen | `extract.v2 transfer` | 12/12 | 71/72 | 1/72 | 73/73 | 10/12 | 2/12 | 10/12 | 0/12 | 1/1 | 0/12 | 0 | 15335 / 3330 | 13986 / 17710 ms |

- **Decision:** extraction → qwen → `extract.v2 transfer`
- **Why:** both models validated 12/12 and recalled 71/72 required fields. Qwen led on citations (73/73 vs 49/76), unsupported-field avoidance (10/12 vs 7/12), version selection (1/1 vs 0/1), token use, and case latency.
- **Rejected:** mistral / `extract.v2` because its citation, unsupported-field, and version-selection results were weaker.
- **Reopen if:** citation matching rules change, a larger case set changes version-selection behavior, the prompt/model tag changes, or deployment hardware changes the latency result.

## Triage

| Model | Prompt | Valid | Queue | Escalation | Missed esc. | Extra esc. | Human boundary | PII | Repairs | Failures | In / out tokens | Median / max case latency |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| mistral | `triage.v1` | 12/12 | 10/12 | 11/12 | 1/12 | 0/12 | 12/12 | 0/12 | 1/12 | 0 | 10849 / 1331 | 4709 / 9408 ms |
| qwen | `triage.v1 transfer` | 12/12 | 12/12 | 12/12 | 0/12 | 0/12 | 12/12 | 0/12 | 0/12 | 0 | 8551 / 852 | 3842 / 6304 ms |

Human-boundary passed on both models. No `draft_reply` promised a refund, approved or denied a claim, or stated that the case was resolved.

- **Decision:** triage → qwen → `triage.v1 transfer`
- **Why:** Qwen achieved 12/12 queue and escalation accuracy, passed both safety metrics, used fewer tokens, required no repair, and had lower case latency.
- **Rejected:** mistral / `triage.v1` because it had two queue errors, one missed escalation, and one repair.
- **Reopen if:** a hard safety metric fails, prompt/model tags change, a larger case set changes routing accuracy, or deployment hardware changes latency materially.

## Limitations

- Each task has only 12 cases. Counts are directional evidence, not production-scale estimates, and a one-case difference does not prove universal model superiority.
- Qwen rows are prompt-transfer / unadapted. No Qwen-specific prompt was measured; adapted prompts would compare model + prompt configurations.
- Untested model/prompt combinations remain untested and should not be inferred from these rows.
- Failed structured outputs would remain visible in the 12-case population and be excluded from deterministic field-metric denominators; this final run had no failures.
- Case latency sums recorded attempts for each evaluation and depends on this machine and its load.
- No production-reliability claim is made. The provider/API charge for these local Ollama calls was `$0.00`.
