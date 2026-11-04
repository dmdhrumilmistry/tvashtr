"""HumanEval harness: hidden official tests for scoring, docstring examples as the only visible tests."""
import ast
import builtins
import gzip
import json
import re
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import sandbox
from .llm import LLM, Usage
from .strategies import STRATEGIES, Task

HUMANEVAL_URL = "https://github.com/openai/human-eval/raw/master/data/HumanEval.jsonl.gz"
DATA = Path(__file__).resolve().parent.parent / "data"
RESULTS = Path(__file__).resolve().parent.parent / "results"


def load_humaneval():
    path = DATA / "HumanEval.jsonl.gz"
    if not path.exists():
        DATA.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(HUMANEVAL_URL, path)
    with gzip.open(path, "rt", encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def split(problems, part):
    """Deterministic dev/test split so strategy selection is never scored on the problems it was tuned on."""
    if part == "all":
        return problems
    return [p for i, p in enumerate(problems) if (i % 2 == 0) == (part == "dev")]


ARROW = re.compile(r"^\s*(?:>>>\s*)?({name}\(.*\))\s*(?:==>|==|➞|=>|->|should return|returns?)\s*(.+?)\s*\.?$")


def docstring_tests(prompt, entry):
    """Turn the examples already written in the prompt into assert statements."""
    tests, lines = [], prompt.splitlines()
    arrow = re.compile(ARROW.pattern.format(name=re.escape(entry)))
    for i, line in enumerate(lines):
        s = line.strip()
        if s.startswith(">>> ") and entry in s and i + 1 < len(lines):
            expr, out = s[4:].strip(), lines[i + 1].strip()
            if out and not out.startswith(">>>"):
                tests.append(f"assert {expr} == {out}")
            continue
        m = arrow.match(s)
        if m:
            tests.append(f"assert {m.group(1)} == {m.group(2)}")
    good, known = [], set(dir(builtins)) | {entry}
    for t in tests:
        try:
            tree = ast.parse(t)
        except SyntaxError:
            continue
        # drop examples with free variables (`fib4(n) == ...`) or non-Python literals (`true`)
        if all(n.id in known for n in ast.walk(tree) if isinstance(n, ast.Name)):
            good.append(t)
    return list(dict.fromkeys(good))


def to_task(p):
    return Task(prompt=f"Complete this Python function:\n\n```python\n{p['prompt']}```",
                entry_point=p["entry_point"], public_tests=docstring_tests(p["prompt"], p["entry_point"]),
                prelude=p["prompt"])


def score(p, code):
    prog = f"{p['prompt']}\n{code}\n\n{p['test']}\ncheck({p['entry_point']})\n"
    return sandbox.run(prog, timeout=20).ok


def run(model, strategy, part="test", limit=None, workers=2, params=None, tag=None):
    problems = split(load_humaneval(), part)[:limit]
    RESULTS.mkdir(exist_ok=True)
    name = f"{model.replace(':', '_').replace('/', '_')}__{tag or strategy}__{part}"
    out = RESULTS / f"{name}.jsonl"
    done = {}
    if out.exists():
        rows = [json.loads(l) for l in out.read_text(encoding="utf-8").splitlines() if l.strip()]
        # rows that died on an infrastructure error (not a model failure) are retried on resume
        ok_rows = [r for r in rows if not any(str(t).startswith("error:") for t in r.get("trace", []))]
        if len(ok_rows) != len(rows):
            out.write_text("".join(json.dumps(r) + "\n" for r in ok_rows), encoding="utf-8")
        done = {r["task_id"]: r for r in ok_rows}
    fn, params = STRATEGIES[strategy], params or {}

    def one(p):
        if p["task_id"] in done:
            return done[p["task_id"]]
        usage, t0 = Usage(), time.time()
        llm = LLM(model, usage)
        try:
            res = fn(llm, to_task(p), **params)
            ok, trace, code = score(p, res.code), res.trace, res.code
        except Exception as e:  # a crashed attempt counts as a failure, never aborts the run
            ok, trace, code = False, [f"error: {e}"], ""
        row = {"task_id": p["task_id"], "passed": ok, "seconds": round(time.time() - t0, 1),
               **usage.as_dict(), "trace": trace, "code": code}
        with open(out, "a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")
        return row

    with ThreadPoolExecutor(max_workers=workers) as ex:
        rows = list(ex.map(one, problems))
    n = len(rows)
    summary = {"model": model, "strategy": tag or strategy, "part": part, "n": n,
               "pass@1": round(sum(r["passed"] for r in rows) / max(n, 1), 4),
               "avg_calls": round(sum(r["calls"] for r in rows) / max(n, 1), 2),
               "avg_output_tokens": round(sum(r["output_tokens"] for r in rows) / max(n, 1)),
               "avg_seconds": round(sum(r["seconds"] for r in rows) / max(n, 1), 1)}
    (RESULTS / f"{name}.summary.json").write_text(json.dumps(summary, indent=2))
    return summary
