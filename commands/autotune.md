---
description: Find the best post-training enhancement for a model (tune on dev, confirm on test) and save its profile
argument-hint: <ollama-model> [--limit N]
---

Use the tvashtr skill. Run `autotune` for: $ARGUMENTS

Summarise the dev scores of every strategy, the chosen strategy, and its held-out test score against
`direct`. Mention where the profile was written, and that `serve` now uses it for `tvashtr/<model>`.
