# Tvashtr

> In the Rig Veda, Tvashtr is the divine artisan who forged Indra's vajra and sharpened the tools of the
> gods. This project does the same for open models: it makes the model you already have sharper
> without retraining it.

Tvashtr makes a local Ollama coding model **measurably** better without fine-tuning, in two ways:

1. **Post-training enhancements (PTEs)**: extra inference-time computation around unchanged weights
   (parallel sampling, execution-feedback repair, test synthesis, selection by execution).
2. **Training-free weight updates**: ExPO extrapolation and task-vector arithmetic over checkpoints that
   already exist, producing a new GGUF you can `ollama run`.

Every gain is measured on held-out problems against the unmodified model. Nothing is trained, and none
of your code is used as data.

It ships as a Python package, an Ollama-compatible server, and a Claude Code plugin (skill + slash
commands).

## Why this works

Davidson et al., *AI capabilities can be significantly improved without expensive retraining*
([arXiv 2312.07413](https://arxiv.org/abs/2312.07413)), survey post-training enhancements and find that
most are worth more than 5x, and many more than 20x, the training compute needed to match them, for
under 1% of the training cost. For code specifically:

| Technique | Paper | In Tvashtr |
|---|---|---|
| Self-planning | Jiang et al. 2023, [arXiv 2303.06689](https://arxiv.org/abs/2303.06689) | `plan` |
| Self-debugging with execution feedback | Chen et al. 2023, [arXiv 2304.05128](https://arxiv.org/abs/2304.05128); Reflexion, [arXiv 2303.11366](https://arxiv.org/abs/2303.11366) | `self_debug` |
| Dual execution agreement over generated tests | CodeT, Chen et al. 2022, [arXiv 2207.10397](https://arxiv.org/abs/2207.10397) | `codet` |
| Parallel + sequential scaling, distinguishing-input selection | S*, Li et al. 2025, [arXiv 2502.14382](https://arxiv.org/abs/2502.14382) | `s_star` |
| Execution feedback matters most for small models | [arXiv 2604.21950](https://arxiv.org/abs/2604.21950) | motivates `adaptive` |
| One-round refinement gains vanish on strong models | [doi 10.3390/ai7090353](https://doi.org/10.3390/ai7090353) | motivates `autotune` |
| Weak-to-strong extrapolation (ExPO) | Zheng et al. 2024, [arXiv 2404.16792](https://arxiv.org/abs/2404.16792) | `expo`, `expo-gguf` |
| Task arithmetic | Ilharco et al. 2023, [arXiv 2212.04089](https://arxiv.org/abs/2212.04089) | `--donor` |

**What Tvashtr adds:**
- **`adaptive` escalation:** a greedy answer is checked against the prompt's own examples plus
  model-written tests. Only if that check fails does it escalate to the full S\* search, seeded with the
  first attempt. Easy tasks cost 2 calls; hard ones get the search.
- **Per-model autotuning:** the literature disagrees on which PTE helps which model, so Tvashtr picks
  one by measurement. It tunes on one half of HumanEval and reports on the other.
- **ExPO on Ollama's own fp16 GGUFs:** no torch, converter or GPU needed, and the controls use the same
  quantization, so a comparison measures the weights rather than the quantizer.

## Results

Held-out half of HumanEval (82 problems, official hidden tests). Hardware: i9-14900K, 32 GB RAM, RTX 3060 12 GB.

| Model | Strategy | pass@1 | avg calls | avg output tokens |
|---|---|---|---|---|
| qwen3-coder:30b | direct | 92.7% | 1.0 | 186 |
| qwen3-coder:30b | adaptive | *running* | | |

ExPO sweep on Qwen2.5-Coder-1.5B: *running*.

Results in `results/` are raw JSONL, one row per problem, so every number can be re-checked.

## Install

```bash
git clone https://github.com/dmdhrumilmistry/tvashtr && cd tvashtr
uv venv .venv && uv pip install --python .venv -e .     # or python -m venv .venv && pip install -e .
ollama pull qwen3-coder:30b                               # or any coding model
```

### As a Claude Code plugin

```
/plugin marketplace add dmdhrumilmistry/tvashtr
/plugin install tvashtr@tvashtr
```

This adds the `tvashtr` skill and the `/tvashtr:bench`, `/tvashtr:autotune`, `/tvashtr:serve` and
`/tvashtr:expo` commands.

## Usage

```bash
python -m tvashtr bench    --model qwen3-coder:30b --strategy direct   --part test
python -m tvashtr bench    --model qwen3-coder:30b --strategy adaptive --part test
python -m tvashtr autotune --model qwen3-coder:30b            # writes profiles/<model>.json
python -m tvashtr serve    --port 11435                       # then use model tvashtr/qwen3-coder:30b
```

### Use it from your editor or agent

Point any Ollama client at `http://127.0.0.1:11435` (OpenAI-compatible clients use `/v1`) and choose a
`tvashtr/<model>` name.
- **Enhanced:** Python code-writing requests go through the model's tuned strategy.
- **Passed through to Ollama unchanged:** tool and agent calls, FIM autocomplete, explanations, other
  languages, and plain model names.

```yaml
# Continue (~/.continue/config.yaml)
models:
  - name: qwen3-coder 30B (tvashtr)
    provider: ollama
    apiBase: http://127.0.0.1:11435
    model: tvashtr/qwen3-coder:30b
    roles: [chat, edit]
```

### Training-free weight updates

```bash
# ExPO: theta = theta_instruct + alpha * (theta_instruct - theta_base), straight from Ollama tags
ollama pull qwen2.5-coder:7b-base-fp16
ollama pull qwen2.5-coder:7b-instruct-fp16
python -m tvashtr expo-gguf --base qwen2.5-coder:7b-base-fp16 --instruct qwen2.5-coder:7b-instruct-fp16 \
    --alpha 0.3 --out models/qc7-expo-0.3.gguf --name qc7-expo:0.3 --quantize q4_K_M
python -m tvashtr bench --model qc7-expo:0.3 --strategy direct --part dev
```

- **Add a donor:** `--donor <tag-or-gguf>:<beta>` adds another same-family fine-tune as a task vector.
- **Safetensors checkpoints:** use `expo --base DIR --instruct DIR`.
- **Always compare against a control:** the original instruct model, imported the same way. Alpha 0 is
  a valid result.

## Safety notes

- **Sandbox:** generated code runs in a temporary directory with a timeout, an isolated interpreter and
  a scrubbed environment. That is process isolation, not a security boundary. Set
  `TVASHTR_SANDBOX=docker` to run each program in a disposable container with no network.
- **Benchmark data:** HumanEval is downloaded from the official OpenAI repository on first use.

## Layout

```
tvashtr/strategies.py   PTEs: direct, plan, self_debug, codet, s_star, adaptive
tvashtr/sandbox.py      execution, test running, output signatures
tvashtr/bench.py        HumanEval harness, dev/test split, docstring-example extraction
tvashtr/autotune.py     per-model strategy selection
tvashtr/server.py       Ollama + OpenAI compatible enhanced endpoint
tvashtr/weights.py      ExPO / task arithmetic on safetensors and GGUF
skills/ commands/ .claude-plugin/   Claude Code plugin
```

## License

Apache-2.0. Model weights you produce inherit their base models' licences.
