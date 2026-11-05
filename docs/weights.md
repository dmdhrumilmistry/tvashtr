---
title: Weights
nav_order: 5
---

# Training-free weight updates
{: .no_toc }

These produce a **new model file**. No gradients, no GPU: tensors stream through numpy in 64 MB
chunks, so a 7B merge needs a few GB of RAM. The result is a normal GGUF that Ollama, llama.cpp,
LM Studio and phone apps can load.

1. TOC
{:toc}

## The idea: task vectors

A fine-tune is a base model plus a difference. That difference, the **task vector**, can be scaled,
added to another model, or extrapolated.

```mermaid
flowchart LR
    B((base)) -->|"+ tau_instruct"| I((instruct))
    B -->|"+ tau_security"| S((security fine-tune))
    I -->|"+ beta x tau_security"| M((instruct + security))
    I -->|"+ alpha x tau_instruct"| E((ExPO: extrapolated))
```

| Method | Formula | Paper |
|---|---|---|
| ExPO | `theta = I + alpha * (I - B)` | Zheng et al. 2024, arXiv 2404.16792 |
| Task arithmetic | `theta = T + beta * (D - B)` | Ilharco et al. 2023, arXiv 2212.04089 |
| DARE | drop a fraction `p` of delta entries at random, rescale the rest by `1/(1-p)` | Yu et al. 2024, arXiv 2311.03099 |

## Pipeline

```mermaid
flowchart TB
    subgraph Inputs
        OB[(Ollama fp16 GGUF<br/>base)]
        OI[(Ollama fp16 GGUF<br/>instruct)]
        HF[(Hugging Face safetensors<br/>donor fine-tune)]
    end
    OB & OI --> R["GGUF reader<br/>(header parsed, tensors memory-mapped)"]
    HF --> SR["safetensors reader<br/>(bf16 -> f32 per chunk)"]
    R & SR --> MAP["name map<br/>blk.N.attn_q.weight <-> model.layers.N.self_attn.q_proj.weight"]
    MAP --> MATH["per 64 MB chunk:<br/>theta = T + beta * DARE(D - B)"]
    MATH --> W["writer: copy target header byte for byte,<br/>rewrite tensor data in its original dtype"]
    W --> G[(new GGUF)]
    G -->|"ollama create (template from instruct)"| O[(Ollama model)]
    O --> EV[bench + secbench on dev] --> SEL{beats control?} -->|yes| PUB[confirm on test, publish]
    SEL -->|no| KEEP[keep original]
```

Why it is built this way:
- **Recent Ollama cannot import Qwen2 safetensors** (it reports "unsupported MLX architecture"), and
  external converters were not an option. So the tool works directly on the fp16 GGUFs Ollama already
  serves, and reads donors as safetensors.
- **Copying the target's header verbatim** keeps the tokenizer, chat template and tensor layout
  exact. Only the numbers change.
- **Every variant is compared against a control:** the unmodified target registered the same way.
  This separates the effect of the weights from the effect of quantization.

## Results so far

| Experiment | Outcome |
|---|---|
| ExPO on Qwen2.5-Coder 0.5B | hurts. Alpha 0.1: -10 problems; alpha 0.3 or above collapses the model |
| ExPO on Qwen2.5-Coder 1.5B | within noise for every alpha |
| ExPO on Qwen2.5-Coder 7B | alpha 0.1 identical to the original; larger alphas are worse |
| Graft DeepHat-V1-7B (security fine-tune of Qwen2.5-Coder-7B) onto Qwen2.5-Coder-7B-Instruct | no variant worth shipping: every graft costs 2-6 coding problems, and DeepHat's CWE-mapping gain does not transfer |

### Graft sweep (dev halves)

| Model | HumanEval | CyberMetric | CTI-MCQ | CTI-RCM |
|---|---|---|---|---|
| Qwen2.5-Coder-7B-Instruct (control) | **91.5%** | 88.8% | 63.3% | 62.0% |
| DeepHat-V1-7B alone | 84.1% | 85.2% | **69.3%** | **83.0%** |
| beta 0.3 | 89.0% | **90.4%** | 63.3% | 64.0% |
| beta 0.7 | 86.6% | 90.0% | 66.7% | 62.0% |
| beta 1.0 | 85.4% | 90.0% | 64.0% | 61.0% |
| beta 0.5, DARE 0.9 | 85.4% | 90.0% | 63.3% | 62.0% |
| beta 1.0, DARE 0.9 | 86.6% | 89.6% | 64.0% | 64.0% |

**Why the security skill did not transfer:**
- **What DeepHat's gain actually is:** in 9 of its 22 CWE-mapping wins, the instruct model answered
  the parent class CWE-119 and DeepHat answered the specific child that NVD assigns (CWE-787, CWE-121,
  CWE-120). That is a labelling convention, possibly learned from these very CVEs, not deeper
  knowledge. Inside a merge the instruct model's answer style wins.
- **It is not interference:** the two task vectors are nearly orthogonal (cosine about 0.05), so
  a different merge rule (TIES, DARE) has nothing to resolve. DARE 0.9 simply dropped the skill.
- **What to do instead:** route CWE questions to the best measured model, or use the retrieval
  strategies, which supply the same specificity from MITRE's catalogue.

**Why ExPO did not help:** it was proposed for extrapolating a small preference step (SFT -> DPO).
Qwen2.5-Coder's base -> instruct step bundles large-scale SFT and RL, so extrapolating past it
overshoots.

## Commands

```bash
# ExPO sweep with control, dev selection and test confirmation
python -m tvashtr expo-sweep --base qwen2.5-coder:7b-base-fp16 --instruct qwen2.5-coder:7b-instruct-fp16 \
    --prefix qc7 --alphas 0.1,0.3,0.5

# graft a security fine-tune's task vector onto the instruct model (with DARE)
python -m tvashtr graft --base qwen2.5-coder:7b-base-fp16 --target qwen2.5-coder:7b-instruct-fp16 \
    --donor D:/models/DeepHat-V1-7B --beta 0.5 --dare 0.9 --out models/coder-sec.gguf --name coder-sec:b0.5
```
