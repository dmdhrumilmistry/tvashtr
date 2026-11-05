"""Pick the best post-training enhancement for a model on the dev split, then confirm it on test.

Research shows the payoff of each PTE depends on the model (self-debugging helps small Qwen2.5
models but barely moves Qwen3-Coder), so Tvashtr measures instead of assuming.
"""
import json

from . import bench
from .server import PROFILES


def tune(model, strategies, limit=None, workers=2):
    dev = {s: bench.run(model, s, "dev", limit, workers) for s in strategies}
    base = dev.get("direct", {}).get("pass@1", 0)
    # best accuracy; among near-ties (within one problem) prefer the cheaper strategy
    n = max(d["n"] for d in dev.values())
    top = max(d["pass@1"] for d in dev.values())
    near = [d for d in dev.values() if d["pass@1"] >= top - 1 / max(n, 1) - 1e-3]  # rounding-safe tie band
    best = min(near, key=lambda d: d["avg_output_tokens"])
    test = bench.run(model, best["strategy"], "test", limit, workers)
    test_direct = bench.run(model, "direct", "test", limit, workers)
    prof = {"model": model, "strategy": best["strategy"], "params": {},
            "dev": dev, "test": {"chosen": test, "direct": test_direct},
            "dev_gain_vs_direct": round(best["pass@1"] - base, 4),
            "test_gain_vs_direct": round(test["pass@1"] - test_direct["pass@1"], 4)}
    PROFILES.mkdir(exist_ok=True)
    (PROFILES / f"{model.replace(':', '_').replace('/', '_')}.json").write_text(json.dumps(prof, indent=2))
    return prof
