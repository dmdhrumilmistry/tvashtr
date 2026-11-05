# Security enhancement plan (no retraining)

Goal: make local models better at cyber-security work without changing their training. Keep every
improvement usable from Ollama and OpenAI-compatible tools, and prove each one on held-out questions.

## Baseline (held-out, direct answer unless noted)

| Benchmark | Foundation-Sec-8B | qwen3:14b | gpt-oss:20b |
|---|---|---|---|
| CyberMetric-500 (250) | 81.6% | 90.4% | 90.8% |
| CTIBench CTI-MCQ (150) | 54.7% | 68.7% | (running) |
| CTIBench CTI-RCM (100) | 59.0% (cot) | 55.0% | (running) |

Refusals: 0% across all models and tasks, so over-refusal is not the bottleneck. Knowledge and
precision are.

What the benchmarks are built from:
- **CTI-MCQ:** generated from MITRE ATT&CK (63%), CWE (22%) and CAPEC (9%) pages.
- **CTI-RCM:** NVD's CWE assignments, covering 104 distinct CWEs. The top 8 account for 55%.

## Levers, ranked by expected value

1. **Retrieval-augmented answering (open book).** Index the public MITRE knowledge bases (CWE,
   CAPEC, ATT&CK Enterprise) with BM25 and put the top-k entries in the prompt.
   - Retrieval was the largest gain in Davidson et al. 2023 (RETRO, CEG 8-43), and analysts work this
     way.
   - **CWE mapping:** a candidate list with definitions turns open recall into choosing from a list.
   - **Query expansion (HyDE):** the model first names the weakness in its own words, then retrieval
     uses description + hypothesis.
   - **NVD view:** restrict CWE candidates to the CWE-1003 view NVD maps to. This reduces distractors.
2. **Model routing (mixture of local models).** Each model wins different tasks (qwen3 knowledge,
   Foundation-Sec CWE mapping). A router sends each request type to its measured best model + strategy.
3. **Cross-model ensemble.** Majority vote over the three models for MCQ-style questions. This only
   pays off when the models' errors are uncorrelated.
4. **Weight merging.** Foundation-Sec-8B is Llama-3.1-8B based, so a linear merge with
   Llama-3.1-8B-Instruct is possible. Deferred: about 50 GB of fp16 downloads, and ExPO did not help on
   Qwen2.5-Coder. Worth trying only if routing + RAG leave a gap.

## Integrity rules

- **Only the public MITRE knowledge bases are indexed,** never benchmark questions or answers.
- **Open-book scores are reported separately from closed-book ones.** CTI-MCQ questions were generated
  from ATT&CK/CWE/CAPEC pages, so retrieval there is closer to an open-book exam: legitimate for
  analyst use, but not comparable to closed-book numbers.
- **Strategies are chosen on dev and reported on test,** the same split as before.
- **Retriever quality is measured on its own** (recall@k on dev) before any model is involved.

## Implementation

| Step | Deliverable |
|---|---|
| 1 | `tvashtr/kb.py`: download CWE / CAPEC / ATT&CK, parse, BM25 index (pure Python), `search()` |
| 2 | Retriever recall@k on CTI-RCM dev, with and without the NVD view and HyDE |
| 3 | `secbench` strategies `rag` and `rag_cot`, plus `ensemble` |
| 4 | `sectune` across models -> `profiles/security-router.json` (best model + strategy per task) |
| 5 | Server: `tvashtr/security` virtual model routes by task type and adds retrieval; works from Ollama, Continue, Open WebUI |
| 6 | Ollama Modelfiles with tuned system prompts for each base, published to ollama.com |
| 7 | README results, charts, commit, push |
