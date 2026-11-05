---
title: Architecture
nav_order: 2
---

# Architecture
{: .no_toc }

1. TOC
{:toc}

## Components

**Online path** (serving requests):

```mermaid
flowchart LR
    CL["Clients<br/>Continue, Aider,<br/>Open WebUI, curl"] --> SV["server.py<br/>Ollama + OpenAI API"]
    SV --> RT["router.py<br/>classify task"]
    RT -->|coding| ST["strategies.py<br/>S*, CodeT, self-debug"]
    ST --> SB["sandbox.py<br/>run code + tests"]
    RT -->|security| KB["kb.py<br/>MITRE CWE, CAPEC,<br/>ATT&CK + BM25F"]
    ST --> OL[("Ollama<br/>GGUF models")]
    KB --> OL
    SV -->|everything else| OL
```

**Offline path** (measuring and building):

```mermaid
flowchart LR
    BE["bench.py / secbench.py<br/>HumanEval, CyberMetric,<br/>CTIBench"] --> RS[("results/<br/>per-problem JSONL")]
    RS --> AT["autotune / sectune /<br/>router build"]
    AT --> PR[("profiles/<br/>router.json")]
    RS --> CMP["compare / rescore"]
    WT["weights.py + sweep.py<br/>ExPO, graft, DARE"] -->|"ollama create"| OL[("Ollama")]
    OL --> BE
    PR -->|used by| SRV["server.py"]
```

The Claude Code plugin (skill plus `/tvashtr:*` commands) drives the offline path from chat.

| Module | Responsibility |
|---|---|
| `llm.py` | Minimal Ollama client: token accounting, retries with backoff on 5xx, `think` control for reasoning models |
| `sandbox.py` | Runs model-written Python in a temp dir with a timeout. Extracts code (CRLF-safe), runs assert lists, and computes output signatures for S\* clustering |
| `strategies.py` | The inference-time enhancements for code |
| `bench.py` | HumanEval loader, deterministic dev/test split, docstring examples as public tests, resumable runs |
| `secbench.py` | Security benchmarks plus MCQ and CWE strategies (reasoning, self-consistency, retrieval) |
| `kb.py` | Downloads and parses the MITRE catalogues, BM25F index, CWE view expansion |
| `router.py` | Builds `profiles/router.json` from dev scores and classifies live requests into tasks |
| `server.py` | HTTP server speaking the Ollama and OpenAI APIs; passthrough for everything it does not enhance |
| `weights.py` | Streaming safetensors and GGUF readers/writers, ExPO, cross-format task arithmetic, DARE |
| `sweep.py` | Controlled weight experiments: control vs variants, dev selection, test confirmation |
| `compare.py`, `rescore.py` | Improved / regressed problem lists with failure types; re-score after harness fixes |

## Request flow through the server

```mermaid
sequenceDiagram
    autonumber
    participant Client as Client (Ollama/OpenAI API)
    participant Server as tvashtr serve
    participant Router as router.classify
    participant Strat as strategy / kb
    participant Ollama as Ollama
    Client->>Server: POST /api/chat model=tvashtr/auto
    Server->>Router: last user message + is_code_request
    Router-->>Server: task (coding / cwe_mapping / threat_intel / security_knowledge / general)
    Server->>Server: look up profiles/router.json -> model + strategy
    alt coding with a search strategy
        Server->>Strat: run S* / CodeT (many Ollama calls + sandbox)
        Strat->>Ollama: samples, repairs, judges
        Strat-->>Server: selected code
        Server-->>Client: one response (stream or not)
    else security with retrieval
        Server->>Strat: kb.search (+ HyDE hypothesis for CWE)
        Strat-->>Server: MITRE reference context
        Server->>Ollama: original request + system context (streamed)
        Ollama-->>Client: tokens stream straight through
    else anything else
        Server->>Ollama: proxy unchanged
        Ollama-->>Client: stream
    end
```

Design rules:
- **Never break the client.** Tool calls, FIM autocomplete, images, non-Python code and unknown
  routes are proxied byte-for-byte. If an enhancement throws, the request falls back to the plain model.
- **Streaming is preserved** for retrieval routes, because the context is injected and the request
  is forwarded. Search strategies have to finish before they can answer, so they return one chunk.

## Data flow of an experiment

```mermaid
flowchart LR
    D[(Benchmarks<br/>HumanEval, CyberMetric, CTIBench)] -->|deterministic split| DEV[dev half]
    D --> TEST[test half]
    DEV --> RUN1[run every strategy / variant]
    RUN1 --> SEL{best on dev<br/>ties -> cheaper}
    SEL --> RUN2[run chosen + baseline on test]
    TEST --> RUN2
    RUN2 --> REP[summary.json + per-problem JSONL]
    REP --> CMP[compare: improved / regressed / failure types]
    REP --> PROF[profiles/*.json + router.json]
    PROF --> SERVE[tvashtr serve]
```

Every run writes one JSON line per problem (prediction, pass/fail, calls, tokens, seconds, trace), so
runs can resume, be re-scored after a harness fix, and be diffed problem by problem.

## Where things are stored

| Path | Content |
|---|---|
| `data/` | downloaded benchmarks and MITRE catalogues (not committed; licences vary) |
| `results/*.jsonl` | per-problem rows for every run |
| `results/*.summary.json` | aggregate metrics per run |
| `results/compare__*.md` | per-problem diffs |
| `profiles/*.json` | chosen strategy per model; `router.json` for `tvashtr/auto` |
| `docs/charts/*.svg` | charts regenerated by `scripts/make_charts.py` |
