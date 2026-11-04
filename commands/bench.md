---
description: Benchmark a local Ollama model on held-out HumanEval with a Tvashtr strategy
argument-hint: <ollama-model> [strategy] [--limit N]
---

Use the tvashtr skill. Benchmark the model and strategy given in: $ARGUMENTS

If no strategy is given, run `direct` first as the baseline and then `adaptive`. Use `--part test`.
Report pass@1, average calls, average output tokens and average seconds for each run side by side,
and state the gain over `direct` in problems as well as percentage points.
