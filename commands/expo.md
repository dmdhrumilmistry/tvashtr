---
description: Training-free weight update (ExPO extrapolation) of an Ollama model family, with an alpha sweep and held-out evaluation
argument-hint: <family e.g. qwen2.5-coder:7b> [alphas e.g. 0.1,0.3,0.5]
---

Use the tvashtr skill. Run an ExPO weight-update experiment for: $ARGUMENTS

1. Pull the family's `-base-fp16` and `-instruct-fp16` tags (into a D:-backed Ollama store if C: is low).
2. Register the unmodified instruct GGUF the same way as the variants, as the control.
3. For each alpha, run `expo-gguf` and create a model, then `bench --strategy direct --part dev`.
4. Take the best variant only if it beats the control on dev, then confirm on `--part test`.

Report a table of alpha against dev and test pass@1, and recommend one, which may be "keep the original".
