---
name: tvashtr
description: Make a local Ollama coding model measurably better without training it - test-time enhancements (S*-style parallel sampling + execution-feedback repair + distinguishing-input selection, CodeT, self-planning, adaptive escalation) and training-free weight updates (ExPO extrapolation, task-vector merging) - then benchmark, autotune and serve the result behind an Ollama-compatible endpoint. Use when the user wants to improve, enhance, boost or "update the weights of" a local/open model for coding without fine-tuning, wants post-training enhancements, model merging or ExPO, wants to benchmark local models on HumanEval, or wants an enhanced model usable from Continue, Aider, Open WebUI or any Ollama client.
---

# Tvashtr

Tvashtr improves an existing open model in two complementary ways, and proves each gain on held-out
problems before using it. Nothing is trained and no private code is ever used as data.

* **Post-training enhancements (PTEs)** - extra inference-time computation around the same weights.
  Davidson et al. 2023 (arXiv 2312.07413) find typical PTEs are worth 5-20x+ training compute.
* **Training-free weight updates** - ExPO extrapolation and task arithmetic over checkpoints that
  already exist. Produces a new model file; costs one pass over the weights on CPU.

Source: https://github.com/dmdhrumilmistry/tvashtr (Apache-2.0).

## Setup (once)

The Python package ships with this plugin: its root is two directories above this SKILL.md
(it contains `pyproject.toml` and `tvashtr/`). If you are working in a clone of the repo, use that
instead. Create a venv there if `.venv` is missing:

```
uv venv .venv && uv pip install --python .venv -e .      # or: python -m venv .venv; pip install -e .
```

Requirements: Python 3.10+, a running Ollama (`ollama serve`), and models pulled.

## Commands

Run from that root with `.venv\Scripts\python.exe -m tvashtr ...` (Windows) or
`.venv/bin/python -m tvashtr ...`.

| Goal | Command |
|---|---|
| Score one strategy | `bench --model qwen3-coder:30b --strategy adaptive --part test` |
| Pick the best strategy for a model | `autotune --model <tag>` (tunes on dev split, confirms on test, writes `profiles/<model>.json`) |
| Serve enhanced models | `serve --port 11435`, then use model `tvashtr/<tag>` at `http://127.0.0.1:11435` |
| ExPO weight update (GGUF, Ollama tags) | `expo-gguf --base <tag>-base-fp16 --instruct <tag>-instruct-fp16 --alpha 0.3 --out D:\models\x.gguf --name <new> --quantize q4_K_M` |
| ExPO on safetensors | `expo --base DIR --instruct DIR --alpha 0.3 --out DIR` |

Strategies: `direct`, `plan`, `self_debug`, `codet`, `s_star`, `adaptive`. Params go in
`--params '{"n": 6, "rounds": 3}'`.

## How to work

1. **Measure first.** Run `bench --strategy direct --part test` as the baseline. Never claim a gain
   without a held-out comparison; report pass@1, avg calls and avg tokens together.
2. **Tune on dev, report on test.** `autotune` keeps selection and reporting on disjoint halves of
   HumanEval. Do not pick a strategy or alpha by looking at test scores.
3. **Weight updates are experiments.** Sweep a few alphas (0.1-0.5), benchmark each with
   `--strategy direct`, and compare against the unmodified model imported the same way (same
   quantization). Keep a variant only if it beats that control on dev and holds up on test.
   Extrapolating base->instruct can hurt; alpha 0 (no change) is a valid winner.
4. **Then stack.** Run `autotune` on the winning weights; weight and inference gains compound.
5. **Serve.** Start `serve`; requests to `tvashtr/<tag>` use the profile. Tool calls, FIM
   autocomplete, explanations and non-Python requests pass straight through.

## Practical notes

* fp16 checkpoints are large (7B is about 15 GB each). If the system drive is short on space, run a
  second Ollama instance with a store on a bigger drive, e.g. `OLLAMA_MODELS=D:\models\ollama`
  `OLLAMA_HOST=127.0.0.1:11436 ollama serve`, and point `OLLAMA_HOST` (CLI) and
  `TVASHTR_UPSTREAM` (bench/serve) at it.
* Recent Ollama builds reject safetensors imports for Qwen2 ("unsupported MLX architecture"), which
  is why `expo-gguf` works on the fp16 GGUF builds from the Ollama library instead.
* Generated code runs in a temp dir with a timeout (`sandbox.py`). That is process isolation, not a
  security boundary; set `TVASHTR_SANDBOX=docker` (Docker running) for untrusted workloads.
* Strong models leave little headroom on HumanEval (qwen3-coder:30b is ~93% direct); gains show up
  most on smaller models and harder problems. Say so rather than overselling small deltas.
