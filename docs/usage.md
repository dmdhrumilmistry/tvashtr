---
title: Usage
nav_order: 7
---

# Usage
{: .no_toc }

1. TOC
{:toc}

## Install

```bash
git clone https://github.com/dmdhrumilmistry/tvashtr && cd tvashtr
uv venv .venv && uv pip install --python .venv -e .     # or: python -m venv .venv && pip install -e .
ollama pull qwen2.5-coder:1.5b
```

Requirements: Python 3.10+ and Ollama. Dependencies are numpy and requests only.

## Claude Code plugin

```
/plugin marketplace add dmdhrumilmistry/tvashtr
/plugin install tvashtr@tvashtr
```

Adds the `tvashtr` skill and `/tvashtr:bench`, `/tvashtr:autotune`, `/tvashtr:serve`, `/tvashtr:expo`.

## Serve enhanced models to your tools

```bash
python -m tvashtr serve --port 11435
```

| Client | Setting |
|---|---|
| Ollama API | base URL `http://127.0.0.1:11435`, model `tvashtr/auto` or `tvashtr/<model>` |
| OpenAI API | base URL `http://127.0.0.1:11435/v1` |
| Continue | `provider: ollama`, `apiBase: http://127.0.0.1:11435`, `model: tvashtr/auto` |
| Aider | `OLLAMA_API_BASE=http://127.0.0.1:11435 aider --model ollama_chat/tvashtr/auto` |

## CLI reference

| Command | Purpose |
|---|---|
| `bench --model M --strategy S --part dev/test` | HumanEval with a strategy |
| `autotune --model M` | choose a coding strategy (dev) and confirm it (test) |
| `secbench --model M --dataset D --strategy S` | one security benchmark run |
| `sectune --model M [--datasets ...] [--strategies ...]` | choose security strategies per dataset |
| `router` | build `profiles/router.json` + `results/scorecard.md` for `tvashtr/auto` |
| `compare A.jsonl B.jsonl` | improved / regressed problems and failure types |
| `rescore results/*.jsonl` | re-score stored outputs after a harness change |
| `expo-sweep`, `expo-gguf`, `expo` | ExPO weight experiments |
| `graft` | task arithmetic + DARE from a safetensors donor onto a GGUF |
| `deploy-check` | score at the shipping quantization and export GGUFs |

## Published models

| Model | Run |
|---|---|
| Qwen2.5-Coder-1.5B + S\* profile | `ollama run dmdhrumilmistry/qwen2.5-coder-tvashtr:1.5b` or `hf.co/dmdhrumilmistry/Qwen2.5-Coder-1.5B-Instruct-Tvashtr-S-star-GGUF:Q4_K_M` |
| ExPO research variants | `dmdhrumilmistry/qwen2.5-coder-expo:{1.5b-alpha0.1, 1.5b-alpha0.3, 7b-alpha0.1}` |

GGUF files on Hugging Face also work in llama.cpp, LM Studio, Jan and phone apps such as PocketPal.
