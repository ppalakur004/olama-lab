Ran all 12 summarization cases on mistral:7b and qwen3:8b under one run (`day2-a0bf960b`). Same prompt, temperature 0.0, and a 256 output-token cap. Both are local Ollama, so `cost_usd` is 0.0 on every line. Not comparing dollars.

**mistral:7b**
- success: 12/12
- tokens: 2739 in, 1453 out
- latency: median 4623 ms, max 9966 ms

It finished every case with `stop` on the first try. Median output was 114 tokens, so 256 was enough for this prompt.

**qwen3:8b**
- success: 0/12
- tokens: 2391 in, 3072 out
- latency: median 11870.5 ms, max 13985 ms

Every case hit `length`, got `TruncatedResponseError`, and was not retried. Output was 256 every time. Ten answers were empty; two were cut off mid-sentence (S05, S12). Qwen3 thinks by default in Ollama and that thinking counts against the cap. We left the default alone and kept the same 256 for both models.
