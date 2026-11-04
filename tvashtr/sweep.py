"""Controlled ExPO experiment: control vs alpha variants, selected on dev, confirmed on test."""
import json
import subprocess
from pathlib import Path

from . import bench, weights


def _create(gguf, name, template_from, quantize, workdir):
    try:
        weights.ollama_create_gguf(gguf, name, template_from, quantize, modelfile_dir=workdir)
        return quantize
    except subprocess.CalledProcessError:
        if not quantize:
            raise
        print(f"ollama could not quantize to {quantize}; registering unquantized")
        weights.ollama_create_gguf(gguf, name, template_from, None, modelfile_dir=workdir)
        return None


def sweep(base, instruct, alphas, prefix, quantize="q8_0", workdir="models", limit=None, workers=2,
          keep_gguf=False):
    work = Path(workdir)
    work.mkdir(parents=True, exist_ok=True)
    blob_b, blob_i = weights.ollama_blob(base), weights.ollama_blob(instruct)
    report = {"base": base, "instruct": instruct, "quantize": quantize, "dev": {}, "test": {}}

    control = f"{prefix}:control"
    report["quantize"] = _create(blob_i, control, instruct, quantize, work)
    report["dev"]["control"] = bench.run(control, "direct", "dev", limit, workers)
    print(json.dumps(report["dev"]["control"]))

    for a in alphas:
        tag = f"{prefix}:expo-{a}"
        out = work / f"{prefix}-expo-{a}.gguf"
        weights.expo_gguf(blob_b, blob_i, out, a)
        _create(out, tag, instruct, report["quantize"], work)
        if not keep_gguf:
            out.unlink()  # Ollama keeps its own copy in the model store
        report["dev"][f"expo-{a}"] = bench.run(tag, "direct", "dev", limit, workers)
        print(json.dumps(report["dev"][f"expo-{a}"]))

    best = max(report["dev"], key=lambda k: (report["dev"][k]["pass@1"], k == "control"))
    report["best_on_dev"] = best
    report["test"]["control"] = bench.run(control, "direct", "test", limit, workers)
    if best != "control":
        report["test"][best] = bench.run(f"{prefix}:{best}", "direct", "test", limit, workers)
    report["test_gain_vs_control"] = round(
        report["test"][best]["pass@1"] - report["test"]["control"]["pass@1"], 4)
    bench.RESULTS.mkdir(exist_ok=True)
    (bench.RESULTS / f"expo-sweep__{prefix}.json").write_text(json.dumps(report, indent=2))
    return report
