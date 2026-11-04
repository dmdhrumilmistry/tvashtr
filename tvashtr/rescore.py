"""Re-score saved runs from their stored model output (after a harness fix), without regenerating."""
import json
from pathlib import Path

from . import bench, sandbox


def rescore(paths):
    problems = {p["task_id"]: p for p in bench.load_humaneval()}
    changes = {}
    for path in map(Path, paths):
        rows = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
        before = sum(r["passed"] for r in rows)
        for r in rows:
            r["code"] = sandbox.extract_code(r["code"])
            r["passed"] = bench.score(problems[r["task_id"]], r["code"])
        after = sum(r["passed"] for r in rows)
        path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
        summary = path.with_name(path.name.replace(".jsonl", ".summary.json"))
        if summary.exists():
            s = json.loads(summary.read_text())
            s["pass@1"] = round(after / max(len(rows), 1), 4)
            summary.write_text(json.dumps(s, indent=2))
        changes[path.name] = (before, after, len(rows))
        print(f"{path.name}: {before} -> {after} / {len(rows)}")
    return changes
