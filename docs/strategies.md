---
title: Strategies
nav_order: 3
---

# Inference-time enhancements
{: .no_toc }

These change *how* an answer is produced. The weights stay the same. All of them use only what a real
user would provide: the problem statement and the examples written in it.

1. TOC
{:toc}

## direct

One greedy answer. This is the baseline every other strategy has to beat.

## plan (self-planning)

```mermaid
flowchart LR
    Q[problem] --> P[LLM: write a numbered plan<br/>no code] --> C[LLM: code following the plan] --> A[answer]
```

**Measured:** -9 problems on Qwen2.5-Coder-1.5B. A small model's plan is often wrong, and it then
follows its own wrong plan faithfully.

## self_debug (execution feedback)

```mermaid
flowchart LR
    Q[problem] --> G[generate code] --> T{run public tests<br/>in sandbox}
    T -->|all pass| A[answer]
    T -->|failure trace| F[LLM: here is the failure,<br/>fix the root cause] --> T2{run again}
    T2 -->|not worse| G2[keep repair] --> T
    T2 -->|worse| A
```

A repair is accepted only if it passes at least as many tests as before, so it can never regress.
**Measured:** +1 on 1.5B. With a single sample there is nothing to choose between.

## codet (dual execution agreement)

```mermaid
flowchart TB
    Q[problem] --> S[N samples, temperature 0.8]
    Q --> T[M model-written asserts]
    S --> X[run every sample against every test]
    T --> X
    X --> CL[group samples by the exact set of tests they pass]
    CL --> SC[score = samples in group x tests passed]
    SC --> A[answer = a sample from the best group]
```

Model-written tests are individually unreliable. CodeT's insight is that agreement between independent
samples and independent tests is reliable. **Measured:** +8 on 1.5B dev at about 6 calls.

## s_star (S\*: parallel + sequential scaling)

```mermaid
flowchart TB
    Q[problem + public tests] --> P1[sample 1] & P2[sample 2] & P3[sample 3] & P4[sample 4]
    P1 --> D1[debug rounds] 
    P2 --> D2[debug rounds]
    P3 --> D3[debug rounds]
    P4 --> D4[debug rounds]
    D1 & D2 & D3 & D4 --> F[finalists = best public-test score]
    F -->|one finalist| A[answer]
    F -->|several| I[LLM synthesizes distinguishing inputs]
    I --> R[run each finalist on those inputs]
    R --> K[cluster by output signature]
    K -->|clear majority| A
    K -->|tie between top clusters| J[LLM judge: which output is correct<br/>for the disagreeing inputs?] --> A
```

**Measured:** 1.5B held-out **70.7% -> 80.5%** (12 fixed, 4 broken, all crashes eliminated), at about
8.5 calls and 24x the tokens. This is the strongest coding gain in the project.

## adaptive (Tvashtr's escalation)

```mermaid
flowchart LR
    Q[problem] --> G[greedy answer] --> V{public tests pass<br/>and model tests >= M-1?}
    V -->|yes: cheap path, 2 calls| A[answer]
    V -->|no| S[S* seeded with the greedy answer] --> A
```

Spends search compute only where verification fails. It is weaker when the model's own tests share
its misunderstanding: then the wrong answer passes verification and never escalates.

## Security strategies (multiple choice and CWE mapping)

| Strategy | How it works |
|---|---|
| `direct` | answer only (letter or CWE ID) |
| `cot` | short reasoning, final `ANSWER:` line. If no parseable answer, one follow-up asks for just the answer (two-stage extraction, Kojima et al. 2022) |
| `sc5` | five sampled `cot` answers, majority vote (self-consistency, Wang et al. 2023) |
| `rag` | retrieve MITRE entries, then answer directly |
| `rag_cot` | retrieve, then reason |
| `rag_hyde` | the model first names the weakness in its own words; retrieval uses description + hypothesis |

How these retrieve: [Security](security.html).

## How a strategy is chosen

`autotune` / `sectune` run every strategy on the **dev** half, take the best one (a one-question tie
goes to the cheaper strategy), then run it and `direct` on the **test** half. Only the test number is
reported. The choice is saved to `profiles/`, and the server uses it.
