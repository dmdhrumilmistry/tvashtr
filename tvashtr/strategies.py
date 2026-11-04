"""Post-training enhancements (PTEs) for code generation. No weights are changed here.

Implemented from the literature (see README for citations):
  direct      - single greedy answer (baseline)
  plan        - self-planning: write a plan, then code to it (Jiang et al. 2023)
  self_debug  - execute against tests, feed the failure back, repair (Chen et al. 2023; Reflexion)
  codet       - N samples x M model-written tests, pick by dual execution agreement (Chen et al. 2022)
  s_star      - parallel samples + sequential debugging + selection by execution on synthesized
                distinguishing inputs (Li et al. 2025, S*)
  adaptive    - Tvashtr's default: greedy answer + cheap verification; escalate to S* only when the
                verification fails. Most easy tasks cost 2 calls, hard ones get the full search.
"""
import re
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from . import sandbox

SYSTEM = ("You are an expert Python engineer. Reply with exactly one complete, self-contained ```python code "
          "block containing the full solution, including imports and any helpers. Keep the requested function "
          "names and signatures. Do not include example usage, tests or explanations.")


@dataclass
class Task:
    prompt: str
    entry_point: str = None
    public_tests: list = field(default_factory=list)   # assert statements visible in the prompt
    prelude: str = ""                                   # e.g. imports the prompt relies on


@dataclass
class Outcome:
    code: str
    strategy: str
    trace: list = field(default_factory=list)


def _program(task, code):
    return f"{task.prelude}\n{code}" if task.prelude else code


def _code_request(task, extra=""):
    return (f"{task.prompt.rstrip()}\n\n{extra}Write the complete implementation"
            + (f" of `{task.entry_point}`" if task.entry_point else "") + ".")


def sample(llm, task, temperature=0.0, seed=None, extra=""):
    return sandbox.extract_code(llm.ask(_code_request(task, extra), system=SYSTEM,
                                        temperature=temperature, seed=seed))


# ---------------------------------------------------------------- test and input synthesis

def gen_tests(llm, task, k=8):
    """Model-written assert statements. Unreliable individually; used for agreement and triage."""
    name = task.entry_point or "the function"
    text = llm.ask(
        f"{task.prompt.rstrip()}\n\nWrite {k} independent Python assert statements that test {name}, covering "
        f"normal cases and edge cases. Compute every expected value carefully by hand from the specification. "
        f"Output only the asserts, one per line, in a ```python block.", temperature=0.2)
    lines = [l.strip() for l in sandbox.extract_code(text).splitlines()]
    tests = [l for l in lines if l.startswith("assert ") and (not task.entry_point or task.entry_point in l)]
    return list(dict.fromkeys(tests))[:k]


def gen_inputs(llm, task, k=8):
    """Distinguishing inputs (S*): call expressions likely to separate subtly different programs."""
    if not task.entry_point:
        return []
    text = llm.ask(
        f"{task.prompt.rstrip()}\n\nWrite {k} diverse, tricky call expressions for `{task.entry_point}` that "
        f"would expose bugs: edge cases, empty inputs, boundaries, duplicates, large or negative values. "
        f"Only valid inputs per the specification. Output only the calls, one per line, like "
        f"`{task.entry_point}(...)`, in a ```python block.", temperature=0.4)
    calls = [l.strip() for l in sandbox.extract_code(text).splitlines()
             if l.strip().startswith(task.entry_point + "(")]
    return list(dict.fromkeys(calls))[:k]


# ---------------------------------------------------------------- strategies

def direct(llm, task, **_):
    return Outcome(sample(llm, task), "direct")


def plan(llm, task, **_):
    steps = llm.ask(f"{task.prompt.rstrip()}\n\nBefore coding, write a short numbered plan: the algorithm, "
                    f"edge cases to handle, and pitfalls in the specification. No code.", temperature=0.0)
    return Outcome(sample(llm, task, extra=f"Follow this plan:\n{steps.strip()}\n\n"), "plan", [steps])


def debug(llm, task, code, tests, rounds=2, temperature=0.0):
    """Repair `code` using execution feedback on `tests`. Returns (code, passed, total)."""
    passed, total, fail = sandbox.run_tests(_program(task, code), tests)
    for _ in range(rounds):
        if not tests or passed == total:
            break
        fixed = sandbox.extract_code(llm.chat([
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": _code_request(task)},
            {"role": "assistant", "content": f"```python\n{code}```"},
            {"role": "user", "content": f"Running it gives this failure:\n\n{fail}\n\n{passed}/{total} checks "
                                        f"passed. Find the root cause, then return the full corrected code."},
        ], temperature=temperature))
        p2, t2, f2 = sandbox.run_tests(_program(task, fixed), tests)
        if p2 >= passed:  # never accept a repair that makes things worse
            code, passed, fail = fixed, p2, f2
    return code, passed, total


def self_debug(llm, task, rounds=2, **_):
    tests = task.public_tests or gen_tests(llm, task)
    code, p, t = debug(llm, task, sample(llm, task), tests, rounds)
    return Outcome(code, "self_debug", [f"{p}/{t}"])


def _parallel(fn, n, workers):
    with ThreadPoolExecutor(max_workers=max(1, min(n, workers))) as ex:
        return list(ex.map(fn, range(n)))


def codet(llm, task, n=5, k=8, workers=4, **_):
    cands = list(dict.fromkeys(_parallel(lambda i: sample(llm, task, 0.8, seed=i), n, workers)))
    tests = list(dict.fromkeys(task.public_tests + gen_tests(llm, task, k)))
    passing = {}
    for c in cands:
        prog = _program(task, c)
        passing[c] = frozenset(t for t in tests if sandbox.run_tests(prog, [t])[0] == 1)
    groups = defaultdict(list)
    for c, s in passing.items():
        groups[s].append(c)
    best = max(groups.items(), key=lambda kv: (len(kv[1]) * len(kv[0]), len(kv[0])))
    return Outcome(best[1][0], "codet", [f"{len(cands)} cands, {len(tests)} tests, best={len(best[0])}"])


def select(llm, task, cands, inputs):
    """S* selection: cluster by execution outputs; the LLM adjudicates between the top two clusters."""
    if len(cands) == 1 or not inputs:
        return cands[0], "single"
    sig = {c: sandbox.outputs_on(_program(task, c), inputs) for c in cands}
    clusters = defaultdict(list)
    for c, s in sig.items():
        clusters[s].append(c)
    ranked = sorted(clusters.items(), key=lambda kv: (-len(kv[1]), sum(o.startswith(("EXC", "CRASH")) for o in kv[0])))
    if len(ranked) == 1 or len(ranked[0][1]) > len(ranked[1][1]):
        return ranked[0][1][0], f"majority {len(ranked[0][1])}/{len(cands)}"
    (sa, ca), (sb, cb) = ranked[0], ranked[1]
    diff = [f"{i}\n  A -> {a}\n  B -> {b}" for i, a, b in zip(inputs, sa, sb) if a != b][:6]
    verdict = llm.ask(
        f"{task.prompt.rstrip()}\n\nTwo implementations disagree on these inputs:\n\n" + "\n".join(diff) +
        "\n\nWork out from the specification what the correct output is for each input, then answer with a "
        "final line `ANSWER: A` or `ANSWER: B`.", temperature=0.0)
    pick = ca[0] if re.search(r"ANSWER:\s*A\b", verdict) else cb[0]
    return pick, "judge"


def s_star(llm, task, n=4, rounds=2, workers=4, seed_code=None, **_):
    tests = task.public_tests or gen_tests(llm, task)

    def one(i):
        c = seed_code if (i == 0 and seed_code) else sample(llm, task, 0.7, seed=100 + i)
        return debug(llm, task, c, tests, rounds, temperature=0.2)

    results = _parallel(one, n, workers)
    top = max(p for _, p, _ in results)
    finalists = list(dict.fromkeys(c for c, p, _ in results if p == top))
    code, how = select(llm, task, finalists, gen_inputs(llm, task) if len(finalists) > 1 else [])
    return Outcome(code, "s_star", [f"top {top}/{results[0][2]}", how])


def adaptive(llm, task, n=4, rounds=2, workers=4, **_):
    """Cheap path first; spend search compute only where verification says it is needed."""
    code = sample(llm, task)
    public = task.public_tests
    gen = gen_tests(llm, task, 6)
    pp, pt, _ = sandbox.run_tests(_program(task, code), public)
    gp, gt, _ = sandbox.run_tests(_program(task, code), gen)
    if pp == pt and (gt == 0 or gp >= gt - 1):  # tolerate one wrong model-written test
        return Outcome(code, "adaptive", [f"fast path public {pp}/{pt} gen {gp}/{gt}"])
    task_for_search = Task(task.prompt, task.entry_point, public or gen, task.prelude)
    out = s_star(llm, task_for_search, n=n, rounds=rounds, workers=workers, seed_code=code)
    return Outcome(out.code, "adaptive", [f"escalated public {pp}/{pt} gen {gp}/{gt}"] + out.trace)


STRATEGIES = {"direct": direct, "plan": plan, "self_debug": self_debug, "codet": codet,
              "s_star": s_star, "adaptive": adaptive}
