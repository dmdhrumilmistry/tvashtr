"""Security knowledge benchmarks with post-training enhancements (no training, no benchmark data in prompts).

Datasets (downloaded on first use, not redistributed):
  cybermetric  CyberMetric-500, 4-option MCQ (github.com/cybermetric/CyberMetric)
  cti-mcq      CTIBench CTI-MCQ, 4-option threat-intel MCQ (AI4Sec/cti-bench, CC-BY-NC-SA-4.0)
  cti-rcm      CTIBench CTI-RCM, map a CVE description to its CWE ID (generative, exact match)

Strategies:
  direct  answer only, greedy
  cot     reason briefly, then a final `ANSWER:` line, greedy
  sc5     self-consistency: 5 sampled `cot` answers, majority vote (Wang et al. 2023, arXiv 2203.11171)

Also measured: refusal rate (no parseable answer and refusal language), the over-refusal signal for
security work.
"""
import csv
import json
import random
import re
import time
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .bench import DATA, RESULTS
from .llm import LLM, Usage

SOURCES = {
    "cybermetric": "https://raw.githubusercontent.com/cybermetric/CyberMetric/main/CyberMetric-500-v1.json",
    "cti-mcq": "https://huggingface.co/datasets/AI4Sec/cti-bench/resolve/main/cti-mcq.tsv",
    "cti-rcm": "https://huggingface.co/datasets/AI4Sec/cti-bench/resolve/main/cti-rcm.tsv",
}
SAMPLE = {"cybermetric": None, "cti-mcq": 300, "cti-rcm": 200}  # deterministic subsample size
REFUSAL = re.compile(r"(I can(?:no|')t (?:help|assist|provide)|I(?:'m| am) (?:sorry|unable)|"
                     r"I won'?t|not able to (?:help|assist)|against (?:my|the) (?:guidelines|policy))", re.I)
SYSTEM = ("You are a cybersecurity expert assisting an authorized security professional. "
          "Answer precisely.")


def _fetch(name):
    path = DATA / Path(SOURCES[name]).name
    if not path.exists():
        DATA.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(SOURCES[name], path)
    return path


def load(name):
    path = _fetch(name)
    if name == "cybermetric":
        qs = json.loads(path.read_text(encoding="utf-8"))["questions"]
        items = [{"id": f"cm-{i}", "kind": "mcq", "question": q["question"], "options": q["answers"],
                  "answer": q["solution"].strip().upper()} for i, q in enumerate(qs)]
    else:
        csv.field_size_limit(10 ** 7)
        rows = list(csv.DictReader(open(path, encoding="utf-8"), delimiter="\t"))
        if name == "cti-mcq":
            items = [{"id": f"mcq-{i}", "kind": "mcq", "question": r["Question"],
                      "options": {k: r[f"Option {k}"] for k in "ABCD"}, "answer": r["GT"].strip().upper()}
                     for i, r in enumerate(rows)]
        else:
            items = [{"id": f"rcm-{i}", "kind": "rcm", "question": r["Description"],
                      "answer": r["GT"].strip().upper()} for i, r in enumerate(rows)]
    if SAMPLE[name] and len(items) > SAMPLE[name]:
        items = sorted(random.Random(0).sample(items, SAMPLE[name]), key=lambda x: int(x["id"].split("-")[1]))
    return items


def split(items, part):
    return items if part == "all" else [x for i, x in enumerate(items) if (i % 2 == 0) == (part == "dev")]


def prompt(item, reason):
    if item["kind"] == "mcq":
        opts = "\n".join(f"{k}. {v}" for k, v in item["options"].items())
        body = f"{item['question']}\n\n{opts}\n\n"
        tail = ("Think step by step in at most 5 short sentences, then give the final line exactly as "
                "`ANSWER: <letter>`." if reason else "Reply with only the letter of the correct option.")
    else:
        body = f"Map this CVE description to the most specific CWE.\n\n{item['question']}\n\n"
        tail = ("Think step by step in at most 5 short sentences, then give the final line exactly as "
                "`ANSWER: CWE-<number>`." if reason else "Reply with only the CWE ID, like CWE-79.")
    return body + tail


def parse(item, text):
    text = text or ""
    if item["kind"] == "mcq":
        m = re.findall(r"ANSWER:\s*\**\(?([ABCD])\b", text, re.I) or re.findall(r"\b([ABCD])\b", text.strip()[-40:])
        if m:
            return m[-1].upper()
        # some models name the option instead of its letter: take the option text mentioned last
        low = text.lower()
        hits = {k: low.rfind(v.lower().strip()) for k, v in item["options"].items() if len(v.strip()) > 2}
        hits = {k: pos for k, pos in hits.items() if pos >= 0}
        return max(hits, key=hits.get) if hits else None
    m = re.findall(r"CWE[-\s_]?(\d+)", text, re.I)
    return f"CWE-{m[-1]}" if m else None


def context(item, hypothesis=""):
    """Open-book context from the public MITRE knowledge bases (never benchmark data)."""
    from . import kb
    idx, views = kb.get()
    if item["kind"] == "rcm":
        query = f"{item['question']} {hypothesis}"
        # NVD maps to the CWE-1003 view (93% of NVD labels); add a few unrestricted hits for the rest
        nvd = idx.search(query, k=10, sources={"cwe"}, allow=set(views.get("1003", [])))
        extra = [d for d in idx.search(query, k=6, sources={"cwe"}) if d["id"] not in {x["id"] for x in nvd}][:3]
        return "Candidate CWEs from the MITRE CWE catalogue (ranked by relevance; may not include the answer):\n" \
               + kb.fmt(nvd + extra, 260)
    opts = " ".join(item.get("options", {}).values())
    docs = idx.search(f"{item['question']} {opts}", k=5)
    return "Reference entries from MITRE ATT&CK, CWE and CAPEC (may not all be relevant):\n" + kb.fmt(docs, 600)


def hypothesis(llm, item):
    """HyDE-style query expansion: the model names the weakness before retrieval."""
    return llm.ask(f"In one sentence, name the root-cause software weakness (the coding mistake, not the impact) "
                   f"behind this vulnerability:\n\n{item['question']}", system=SYSTEM, temperature=0.0,
                   max_tokens=60 if llm.think is False else 1024)


def with_context(item, ctx):
    return {**item, "question": f"{ctx}\n\n{'Question' if item['kind'] == 'mcq' else 'CVE description'}: "
                                f"{item['question']}"}


def reasoned(llm, item, temperature, max_tokens, seed=None):
    """Reason, then answer. If the reasoning never states a parseable final answer (e.g. it ends on a
    paraphrase of an option), ask once for just the answer: two-stage extraction (Kojima et al. 2022)."""
    p = prompt(item, True)
    text = llm.ask(p, system=SYSTEM, temperature=temperature, max_tokens=max_tokens, seed=seed)
    pred = parse(item, text)
    if pred is None and not REFUSAL.search(text):
        follow = ("Reply with only the letter (A, B, C or D) of your final answer." if item["kind"] == "mcq"
                  else "Reply with only the CWE ID of your final answer, like CWE-79.")
        again = llm.chat([{"role": "system", "content": SYSTEM}, {"role": "user", "content": p},
                          {"role": "assistant", "content": text}, {"role": "user", "content": follow}],
                         temperature=0.0, max_tokens=24 if llm.think is False else 1024)
        pred, text = parse(item, again), f"{text}\n[extracted] {again}"
    return pred, text


def answer(llm, item, strategy):
    # thinking tokens count against num_predict, so only cap tightly when thinking is off
    short, long_ = (24, 700) if llm.think is False else (2048, 2048)
    if strategy == "direct":
        text = llm.ask(prompt(item, False), system=SYSTEM, temperature=0.0, max_tokens=short)
        return parse(item, text), [text[-200:]]
    if strategy == "cot":
        pred, text = reasoned(llm, item, 0.0, long_)
        return pred, [text[-300:]]
    if strategy in ("rag", "rag_cot", "rag_hyde"):
        hyp = hypothesis(llm, item) if strategy == "rag_hyde" and item["kind"] == "rcm" else ""
        aug = with_context(item, context(item, hyp))
        if strategy == "rag":
            text = llm.ask(prompt(aug, False), system=SYSTEM, temperature=0.0, max_tokens=short)
            pred = parse(item, text)
            if pred is None:  # fall back to reasoning-style extraction
                pred, text = reasoned(llm, aug, 0.0, long_)
            return pred, [text[-200:]]
        pred, text = reasoned(llm, aug, 0.0, long_)
        return pred, [(f"[hyp] {hyp[:150]} " if hyp else "") + text[-250:]]
    if strategy == "sc5":
        with ThreadPoolExecutor(max_workers=2) as ex:
            outs = list(ex.map(lambda i: reasoned(llm, item, 0.7, long_, seed=i), range(5)))
        texts = [t for _, t in outs]
        votes = Counter(p for p, _ in outs if p)
        best = votes.most_common(1)[0][0] if votes else None
        return best, [dict(votes), texts[0][-200:]]
    raise ValueError(strategy)


def run(model, dataset, strategy, part="test", limit=None, workers=2, upstream=None):
    items = split(load(dataset), part)[:limit]
    RESULTS.mkdir(exist_ok=True)
    name = f"sec__{model.replace(':', '_').replace('/', '_')}__{dataset}__{strategy}__{part}"
    out = RESULTS / f"{name}.jsonl"
    done = {}
    if out.exists():
        rows = [json.loads(l) for l in out.read_text(encoding="utf-8").splitlines() if l.strip()]
        ok = [r for r in rows if not any(str(t).startswith("error:") for t in r.get("trace", []))]
        if len(ok) != len(rows):
            out.write_text("".join(json.dumps(r) + "\n" for r in ok), encoding="utf-8")
        done = {r["task_id"]: r for r in ok}

    def one(item):
        if item["id"] in done:
            return done[item["id"]]
        usage, t0 = Usage(), time.time()
        llm = LLM(model, usage, num_ctx=4096, upstream=upstream)
        try:
            pred, trace = answer(llm, item, strategy)
        except Exception as e:
            pred, trace = None, [f"error: {e}"]
        text = " ".join(map(str, trace))
        row = {"task_id": item["id"], "passed": pred == item["answer"], "pred": pred, "gold": item["answer"],
               "refused": pred is None and bool(REFUSAL.search(text)), "seconds": round(time.time() - t0, 1),
               **usage.as_dict(), "trace": trace, "code": ""}
        with open(out, "a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")
        return row

    with ThreadPoolExecutor(max_workers=workers) as ex:
        rows = list(ex.map(one, items))
    n = max(len(rows), 1)
    summary = {"model": model, "dataset": dataset, "strategy": strategy, "part": part, "n": len(rows),
               "accuracy": round(sum(r["passed"] for r in rows) / n, 4),
               "unparsed": round(sum(r["pred"] is None for r in rows) / n, 4),
               "refusal_rate": round(sum(r["refused"] for r in rows) / n, 4),
               "avg_calls": round(sum(r["calls"] for r in rows) / n, 2),
               "avg_output_tokens": round(sum(r["output_tokens"] for r in rows) / n),
               "avg_seconds": round(sum(r["seconds"] for r in rows) / n, 1)}
    (RESULTS / f"{name}.summary.json").write_text(json.dumps(summary, indent=2))
    return summary


def tune(model, datasets=("cybermetric", "cti-mcq", "cti-rcm"), strategies=("direct", "cot", "sc5"),
         dev_limit=None, workers=2, upstream=None):
    """Pick the best strategy per dataset on dev, confirm against direct on test."""
    report = {"model": model, "datasets": {}}
    for ds in datasets:
        dev = {s: run(model, ds, s, "dev", dev_limit, workers, upstream) for s in strategies}
        top = max(d["accuracy"] for d in dev.values())
        n = max(d["n"] for d in dev.values())
        near = [d for d in dev.values() if d["accuracy"] >= top - 1 / max(n, 1)]
        best = min(near, key=lambda d: d["avg_output_tokens"])["strategy"]
        test = {s: run(model, ds, s, "test", None, workers, upstream) for s in dict.fromkeys(["direct", best])}
        report["datasets"][ds] = {"dev": dev, "best": best, "test": test,
                                  "test_gain": round(test[best]["accuracy"] - test["direct"]["accuracy"], 4)}
    (RESULTS / f"sec-tune__{model.replace(':', '_').replace('/', '_')}.json").write_text(json.dumps(report, indent=2))
    return report
