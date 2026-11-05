"""Per-problem diff of two benchmark runs: what improved, what regressed, and why it fails."""
import json
import re
from collections import Counter
from pathlib import Path

from . import bench, sandbox


def load(path):
    rows = [json.loads(l) for l in Path(path).read_text(encoding="utf-8").splitlines() if l.strip()]
    return {r["task_id"]: r for r in rows}


def diagnose(problem, code):
    """Why a solution fails the hidden tests: wrong_answer, timeout, syntax_error, runtime:<Type>, no_code."""
    if problem is None:  # non-code benchmark (e.g. security MCQ): only right/wrong is meaningful
        return "wrong_answer"
    if not code or not code.strip():
        return "no_code"
    try:
        compile(code, "<solution>", "exec")
    except SyntaxError:
        return "syntax_error"
    prog = f"{problem['prompt']}\n{code}\n\n{problem['test']}\ncheck({problem['entry_point']})\n"
    res = sandbox.run(prog, timeout=20)
    if res.ok:
        return "pass"
    if res.timeout:
        return "timeout"
    m = re.findall(r"^(\w+(?:Error|Exception|Exit|Interrupt)):?", res.stderr, re.M)
    if not m:
        return "runtime:unknown"
    return "wrong_answer" if m[-1] == "AssertionError" else f"runtime:{m[-1]}"


def compare(a_path, b_path, out=None):
    a, b = load(a_path), load(b_path)
    problems = {p["task_id"]: p for p in bench.load_humaneval()}
    common = sorted(set(a) & set(b), key=lambda t: (t.rsplit("/", 1)[0].rsplit("-", 1)[0],
                                                       int(re.findall(r"\d+", t)[-1])))

    def label(t):
        p = problems.get(t)
        return f"{t} `{p['entry_point']}`" if p else f"{t} (gold {a[t].get('gold')}, A={a[t].get('pred')}, B={b[t].get('pred')})"
    gained = [t for t in common if b[t]["passed"] and not a[t]["passed"]]
    lost = [t for t in common if a[t]["passed"] and not b[t]["passed"]]
    both_fail = [t for t in common if not a[t]["passed"] and not b[t]["passed"]]
    why = {t: (diagnose(problems.get(t), a[t]["code"]) if t in gained or t in both_fail else None,
               diagnose(problems.get(t), b[t]["code"]) if t in lost or t in both_fail else None)
           for t in gained + lost + both_fail}

    def avg(rows, k):
        return sum(r[k] for r in rows) / max(len(rows), 1)

    ra, rb = [a[t] for t in common], [b[t] for t in common]
    name_a, name_b = Path(a_path).stem, Path(b_path).stem
    lines = [f"# {name_a} vs {name_b}", "",
             f"Problems compared: {len(common)}", "",
             "| | A | B | delta |", "|---|---|---|---|",
             f"| pass@1 | {avg(ra, 'passed'):.1%} | {avg(rb, 'passed'):.1%} | "
             f"{avg(rb, 'passed') - avg(ra, 'passed'):+.1%} ({len(gained) - len(lost):+d} problems) |",
             f"| avg model calls | {avg(ra, 'calls'):.2f} | {avg(rb, 'calls'):.2f} | {avg(rb, 'calls') - avg(ra, 'calls'):+.2f} |",
             f"| avg output tokens | {avg(ra, 'output_tokens'):.0f} | {avg(rb, 'output_tokens'):.0f} | "
             f"{avg(rb, 'output_tokens') - avg(ra, 'output_tokens'):+.0f} |",
             f"| avg seconds | {avg(ra, 'seconds'):.1f} | {avg(rb, 'seconds'):.1f} | {avg(rb, 'seconds') - avg(ra, 'seconds'):+.1f} |",
             "", f"## Improved ({len(gained)}): failed in A, pass in B", ""]
    lines += [f"- {label(t)} - A failed with {why[t][0]}" for t in gained] or ["- none"]
    lines += ["", f"## Regressed ({len(lost)}): pass in A, failed in B", ""]
    lines += [f"- {label(t)} - B fails with {why[t][1]}" for t in lost] or ["- none"]
    lines += ["", f"## Still failing in both ({len(both_fail)})", ""]
    lines += [f"- {label(t)} - A: {why[t][0]}, B: {why[t][1]}" for t in both_fail] or ["- none"]
    fa = Counter(diagnose(problems.get(t), a[t]["code"]) for t in common if not a[t]["passed"])
    fb = Counter(diagnose(problems.get(t), b[t]["code"]) for t in common if not b[t]["passed"])
    lines += ["", "## Failure types", "", "| type | A | B |", "|---|---|---|"]
    lines += [f"| {k} | {fa.get(k, 0)} | {fb.get(k, 0)} |" for k in sorted(set(fa) | set(fb))] or ["| none | 0 | 0 |"]
    text = "\n".join(lines) + "\n"
    out = Path(out) if out else bench.RESULTS / f"compare__{name_a}__vs__{name_b}.md"
    out.write_text(text, encoding="utf-8")
    return text
