"""Publish the S* release: original Qwen2.5-Coder-1.5B-Instruct weights + Tvashtr S* profile.

The measured gain (70.7% -> 80.5% held-out HumanEval) comes from test-time search, not new weights,
so this release ships the original weights (q4_K_M and fp16 GGUF) together with the tuned profile and
instructions. It also writes matching profiles into profiles/, so `tvashtr serve` applies S* to every
published name.

    hf auth login
    OLLAMA_HOST=127.0.0.1:11436 python scripts/publish_sstar.py --hf-user <user> --ollama-user <user>
"""
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from tvashtr import weights  # noqa: E402

RES, PROFILES = ROOT / "results", ROOT / "profiles"
REPO = "https://github.com/dmdhrumilmistry/tvashtr"
SOURCES = {"Q4_K_M": "qwen2.5-coder:1.5b", "F16": "qwen2.5-coder:1.5b-instruct-fp16"}


def summ(strategy, part):
    return json.loads((RES / f"qc15_control__{strategy}__{part}.summary.json").read_text())


def safe(name):
    return name.replace(":", "_").replace("/", "_")


def card(hf_repo, ollama_names):
    d_dev, d_test, s_dev, s_test = summ("direct", "dev"), summ("direct", "test"), summ("s_star", "dev"), summ("s_star", "test")
    rows = "\n".join(
        f"| `{s}` | {summ(s, 'dev')['pass@1']:.1%} | {summ(s, 'dev')['avg_calls']:.1f} | {summ(s, 'dev')['avg_output_tokens']} |"
        for s in ("direct", "plan", "self_debug", "adaptive", "codet", "s_star"))
    return f"""---
license: apache-2.0
base_model: Qwen/Qwen2.5-Coder-1.5B-Instruct
base_model_relation: quantized
tags: [gguf, ollama, code, qwen2.5-coder, test-time-compute, s-star, tvashtr]
---

# Qwen2.5-Coder-1.5B-Instruct + Tvashtr S\\*

**+9.8 points on held-out HumanEval (70.7% -> 80.5%), with no training.** That is close to the plain
7B model (84.2%) at 1.5B memory.

The gain comes from **test-time search** (S\\*, Li et al. 2025, arXiv 2502.14382), applied by
[Tvashtr]({REPO}):
1. sample several candidate solutions in parallel;
2. repair each one with execution feedback on the examples in the prompt;
3. pick the winner by running the finalists on synthesized inputs that tell them apart.

The weights in this repo are the **original** Qwen2.5-Coder-1.5B-Instruct (q4_K_M and fp16 GGUF). Run
them plainly for normal speed, or through Tvashtr for the S\\* accuracy.

## Results (HumanEval, official hidden tests)

| | Single answer | With S\\* |
|---|---|---|
| Held-out test half (82) | {d_test['pass@1']:.1%} ({round(d_test['pass@1'] * 82)}) | **{s_test['pass@1']:.1%} ({round(s_test['pass@1'] * 82)})** |
| Dev half (82, used for selection) | {d_dev['pass@1']:.1%} | {s_dev['pass@1']:.1%} |
| Model calls per problem | 1 | {s_test['avg_calls']:.1f} |
| Seconds per problem (RTX 3060) | {d_test['avg_seconds']} | {s_test['avg_seconds']} |

**What changed on the held-out half:**
- **12 problems fixed and 4 broken**, a net gain of +8.
- **All runtime crashes are gone.**
- **Wrong answers fell from 20 to 15.**

Noise floor: about +/-3 problems.

All strategies, dev half:

| Strategy | pass@1 | Calls | Output tokens |
|---|---|---|---|
{rows}

## Ways to use it

**1. Ollama, plain speed:**
```bash
ollama run {ollama_names[0]}
ollama run hf.co/{hf_repo}:Q4_K_M
```

**2. With S\\*, through any Ollama/OpenAI client** (Continue, Aider, Open WebUI, Cline):
```bash
git clone {REPO} && cd tvashtr && pip install -e .
python -m tvashtr serve --port 11435
# then use base URL http://127.0.0.1:11435 and model  tvashtr/{ollama_names[0]}
```
Python code-writing requests get S\\*. Chat, tool calls and autocomplete pass straight through.

**3. llama.cpp, LM Studio, Jan, GPT4All, or phone apps (PocketPal, ChatterUI):** download
`*-Q4_K_M.gguf` (~0.9 GB, phone friendly) or `*-F16.gguf` (~3 GB). Use plain mode: S\\* needs to
execute code, so it runs on a PC.

**4. Claude Code plugin:** `/plugin marketplace add dmdhrumilmistry/tvashtr`, then
`/plugin install tvashtr@tvashtr`.

The profile used is `tvashtr-profile.json` in this repo.

## License

Apache-2.0, inherited from Qwen2.5-Coder-1.5B-Instruct.
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hf-user", required=True)
    ap.add_argument("--ollama-user", required=True)
    ap.add_argument("--skip-ollama", action="store_true")
    a = ap.parse_args()
    hf_repo = f"{a.hf_user}/Qwen2.5-Coder-1.5B-Instruct-Tvashtr-S-star-GGUF"
    ollama_names = [f"{a.ollama_user}/qwen2.5-coder-tvashtr:1.5b", f"{a.ollama_user}/qwen2.5-coder-tvashtr:1.5b-fp16"]

    # tuned profile under every name a user might serve, so `tvashtr serve` picks S* automatically
    prof = json.loads((PROFILES / "qc15_control.json").read_text())
    prof["note"] = "Tuned on qc15:control (Qwen2.5-Coder-1.5B-Instruct fp16); applies to the same weights."
    names = ollama_names + [f"hf.co/{hf_repo}:Q4_K_M", f"hf.co/{hf_repo}:F16", "qwen2.5-coder:1.5b",
                            "qwen2.5-coder:1.5b-instruct-fp16"]
    for n in names:
        (PROFILES / f"{safe(n)}.json").write_text(json.dumps({**prof, "model": n}, indent=2))

    if not a.skip_ollama:
        for src, dst in zip(SOURCES.values(), ollama_names):
            subprocess.run(["ollama", "cp", src, dst], check=True)
            subprocess.run(["ollama", "push", dst], check=True)
            print(f"pushed https://ollama.com/{dst}")

    from huggingface_hub import HfApi
    api = HfApi()
    api.create_repo(hf_repo, exist_ok=True, private=False)
    msg = "Original Qwen2.5-Coder-1.5B-Instruct GGUF + Tvashtr S* profile and measured card"
    api.upload_file(path_or_fileobj=card(hf_repo, ollama_names).encode(), path_in_repo="README.md",
                    repo_id=hf_repo, commit_message=msg)
    api.upload_file(path_or_fileobj=json.dumps(prof, indent=2).encode(), path_in_repo="tvashtr-profile.json",
                    repo_id=hf_repo, commit_message=msg)
    for quant, src in SOURCES.items():
        api.upload_file(path_or_fileobj=str(weights.ollama_blob(src)), repo_id=hf_repo, commit_message=msg,
                        path_in_repo=f"Qwen2.5-Coder-1.5B-Instruct-{quant}.gguf")
    print(f"published https://huggingface.co/{hf_repo}")


if __name__ == "__main__":
    main()
