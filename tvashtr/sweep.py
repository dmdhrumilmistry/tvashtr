"""Controlled ExPO experiment: control vs alpha variants, selected on dev, confirmed on test."""
import json
import shutil
import subprocess
from pathlib import Path

from . import bench, weights


def _create(gguf, name, template_from, quantize, workdir, allow_unquantized=False):
    """Create the model; never silently ship a different quantization than the one being measured."""
    try:
        weights.ollama_create_gguf(gguf, name, template_from, quantize, modelfile_dir=workdir)
        return quantize
    except subprocess.CalledProcessError:
        if not quantize or not allow_unquantized:
            raise SystemExit(f"ollama create --quantize {quantize} failed for {name}; "
                             f"refusing to measure an unquantized model under a quantized name")
        print(f"ollama could not quantize to {quantize}; registering unquantized (allowed for sweeps)")
        weights.ollama_create_gguf(gguf, name, template_from, None, modelfile_dir=workdir)
        return None


def sweep(base, instruct, alphas, prefix, quantize="q8_0", workdir="models", limit=None, workers=2,
          keep_gguf=False):
    work = Path(workdir)
    work.mkdir(parents=True, exist_ok=True)
    blob_b, blob_i = weights.ollama_blob(base), weights.ollama_blob(instruct)
    report = {"base": base, "instruct": instruct, "quantize": quantize, "dev": {}, "test": {}}

    control = f"{prefix}:control"
    report["quantize"] = _create(blob_i, control, instruct, quantize, work, allow_unquantized=True)
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


def deploy_check(base, instruct, prefix, alpha, quantize="q4_K_M", workdir="models", export_dir=None,
                 limit=None, workers=2):
    """Re-check a variant at the quantization it will ship with (e.g. q4_K_M for phones).

    Low-bit quantization can erase a small weight-space gain, so the control and the variant are both
    rebuilt at `quantize` and scored on the full HumanEval. The resulting GGUFs are exported for
    llama.cpp-based mobile apps (PocketPal, ChatterUI, Ollama in Termux).
    """
    work = Path(workdir)
    work.mkdir(parents=True, exist_ok=True)
    qtag = quantize.lower().replace("_", "")
    blob_b, blob_i = weights.ollama_blob(base), weights.ollama_blob(instruct)
    models = {"control": (blob_i, f"{prefix}:control-{qtag}")}
    if alpha:
        out = work / f"{prefix}-expo-{alpha}.gguf"
        weights.expo_gguf(blob_b, blob_i, out, alpha)
        models[f"expo-{alpha}"] = (out, f"{prefix}:expo-{alpha}-{qtag}")
    report = {"base": base, "instruct": instruct, "quantize": quantize, "alpha": alpha, "runs": {}, "files": {}}
    for key, (src, tag) in models.items():
        _create(src, tag, instruct, quantize, work)
        report["runs"][key] = {part: bench.run(tag, "direct", part, limit, workers) for part in ("dev", "test")}
        if export_dir:
            dst = Path(export_dir) / f"{tag.replace(':', '-')}.gguf"
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(weights.ollama_blob(tag), dst)
            report["files"][key] = {"path": str(dst), "MB": round(dst.stat().st_size / 2**20)}
    if alpha and models[f"expo-{alpha}"][0].exists():
        models[f"expo-{alpha}"][0].unlink()
    (bench.RESULTS / f"deploy-check__{prefix}-{qtag}.json").write_text(json.dumps(report, indent=2))
    return report
