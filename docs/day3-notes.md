Run `day3-752cbbd8` on mistral:7b, temperature 0.0. `summarize.v1` over 12 summarization cases and `extract.v2` over 12 extraction cases. Last reply for every case validated (12/12 and 12/12). Evidence is `docs/day3-run.jsonl`.

- summarization repair rate: 1/12 (S04 only)
- extraction repair rate: 0/12
- example leakage count: 0
- citation-existence failure count: 73

The most common validation error was an EvidenceField missing `value` when status was absent (S05 also added extra keys like attendees). We made schema_description and the summarize prompt require `"value": null` on those fields and forbade extra keys, then reran; S04 still needed one repair, everything else passed on the first try.

Citation check: a `present` field failed if `citation` was not a real heading in that case. Almost all 73 fails are `"1"` / `"2"` instead of `"1. Document Control"`. Leakage: no Northglass, Redhaven, Norwyn, Bellwater, or East Kestrel strings in extraction outputs.
