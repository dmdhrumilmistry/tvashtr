"""Publish ExPO research variants to Hugging Face as GGUF repos, each with a measured model card.

    hf auth login                       # write token, once
    OLLAMA_HOST=127.0.0.1:11436 python scripts/publish_hf.py --user <hf-user> [--dry-run]

Reads the GGUF blob behind each Ollama tag, so nothing is re-exported. Cards are generated from
results/*.summary.json so every number on Hugging Face matches the repo.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from tvashtr import weights  # noqa: E402

RES = ROOT / "results"
REPO = "https://github.com/dmdhrumilmistry/tvashtr"

VARIANTS = [  # (ollama tag, size, alpha, prefix)
    ("qc7:expo-0.1", "7B", 0.1, "qc7"),
    ("qc15:expo-0.1", "1.5B", 0.1, "qc15"),
    ("qc15:expo-0.3", "1.5B", 0.3, "qc15"),
]


def score(model, part):
    p = RES / f"{model.replace(':', '_')}__direct__{part}.summary.json"
    if not p.exists():
        return None
    s = json.loads(p.read_text())
    return round(s["pass@1"] * s["n"]), s["n"], s["pass@1"]


def fmt(s):
    return f"{s[2]:.1%} ({s[0]}/{s[1]})" if s else "not measured"


def card(tag, size, alpha, prefix, ollama_name, hf_repo):
    ctrl = f"{prefix}:control"
    rows = []
    for part, label in (("dev", "dev half (selection)"), ("test", "test half (held out)")):
        rows.append(f"| HumanEval {label} | {fmt(score(ctrl, part))} | {fmt(score(tag, part))} |")
    return f"""---
license: apache-2.0
base_model: Qwen/Qwen2.5-Coder-{size}-Instruct
base_model_relation: merge
tags: [gguf, ollama, code, qwen2.5-coder, expo, model-merging, research]
---

# Qwen2.5-Coder-{size}-Instruct ExPO alpha={alpha} (research release)

**Experimental. Did not beat the original model. Use the original Qwen2.5-Coder-{size}-Instruct for
real work.** Published so the result can be reproduced and built on.

Produced with [Tvashtr]({REPO}), a toolkit for improving local models without training. These weights
are a training-free ExPO extrapolation (Zheng et al. 2024, arXiv 2404.16792) of the official Qwen
checkpoints:

`theta = theta_instruct + {alpha} * (theta_instruct - theta_base)`

It was applied to Ollama's fp16 GGUFs of `qwen2.5-coder:{size.lower()}-base` and `-instruct`. The file is fp16 GGUF.

## Measured results

Scored with the official HumanEval hidden tests, single greedy answer, against the unmodified
instruct model prepared the same way. The noise floor is about +/-3 problems per 82-problem half.

| Benchmark | Original | This model |
|---|---|---|
{chr(10).join(rows)}

**Verdict:** within noise of the original, so there is no reliable gain. Across the sweep, larger
alphas were worse at every size, and Qwen2.5-Coder-0.5B collapsed at alpha 0.3. The likely reason is
that Qwen2.5-Coder's base -> instruct step bundles large-scale SFT and RL, whereas ExPO was proposed
for extrapolating a small preference-optimization step. Full sweep, per-problem diffs and charts are
in the [Tvashtr README]({REPO}#training-free-weight-updates-expo).

The gain that did hold up in the same study comes from test-time search, not weights: S\\* lifts the
original Qwen2.5-Coder-1.5B from 70.7% to 80.5% held-out. Use it via `tvashtr serve`.

## Use

```bash
ollama run {ollama_name}
ollama run hf.co/{hf_repo}:F16
```

## License

Apache-2.0, inherited from Qwen2.5-Coder-{size}.
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", required=True)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--only", help="comma-separated Ollama tags to publish, e.g. qc15:expo-0.1")
    a = ap.parse_args()
    variants = [v for v in VARIANTS if not a.only or v[0] in a.only.split(",")]
    out = ROOT / "docs" / "model-cards"
    out.mkdir(parents=True, exist_ok=True)
    if not a.dry_run:
        from huggingface_hub import HfApi
        api = HfApi()
    for tag, size, alpha, prefix in variants:
        repo = f"{a.user}/Qwen2.5-Coder-{size}-Instruct-ExPO-a{alpha}-GGUF"
        ollama_name = f"dmdhrumilmistry/qwen2.5-coder-expo:{size.lower()}-alpha{alpha}"
        text = card(tag, size, alpha, prefix, ollama_name, repo)
        (out / f"{size.lower()}-alpha{alpha}.md").write_text(text, encoding="utf-8")
        if a.dry_run:
            print(f"[dry-run] {repo}: card written to docs/model-cards/")
            continue
        blob = weights.ollama_blob(tag)
        api.create_repo(repo, exist_ok=True, private=False)
        api.upload_file(path_or_fileobj=text.encode(), path_in_repo="README.md", repo_id=repo,
                        commit_message="Model card with measured results")
        api.upload_file(path_or_fileobj=str(blob),
                        path_in_repo=f"Qwen2.5-Coder-{size}-Instruct-ExPO-a{alpha}-F16.gguf",
                        repo_id=repo, commit_message=f"ExPO alpha={alpha} fp16 GGUF")
        print(f"published https://huggingface.co/{repo}")


if __name__ == "__main__":
    main()
