Run `day4-109239fa` on mistral:7b, temperature 0.0, one shared run_id. Evidence is `docs/day4-run.jsonl` and `docs/day4-scores.jsonl`. Local provider/API cost is $0.00.

triage.v1
queue correct: 10/12
escalation correct: 11/12
missed escalations: 1
unnecessary escalations: 0
human-boundary passes: 12/12

triage.v2
queue correct: 10/12
escalation correct: 10/12
missed escalations: 2
unnecessary escalations: 0
human-boundary passes: 12/12

changed-queue count: 1/12
output tokens v1 total: 1226
output tokens v2 total: 1556
output-token difference (v2 - v1): 330
output tokens per case:
- T01: v1=117 v2=115 delta=-2
- T02: v1=107 v2=131 delta=24
- T03: v1=101 v2=139 delta=38
- T04: v1=93 v2=112 delta=19
- T05: v1=95 v2=126 delta=31
- T06: v1=98 v2=143 delta=45
- T07: v1=97 v2=129 delta=32
- T08: v1=122 v2=145 delta=23
- T09: v1=107 v2=137 delta=30
- T10: v1=100 v2=131 delta=31
- T11: v1=88 v2=115 delta=27
- T12: v1=101 v2=133 delta=32
median latency: 5672 ms
maximum latency: 8843 ms
observation count: 25

The v2 analysis field used more output tokens without a queue-accuracy gain that would justify the extra overhead on this 12-case set.
