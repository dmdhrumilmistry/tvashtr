"""Unified router: one Ollama-compatible model name (`tvashtr/auto`) that sends each request to the model +
strategy measured best for its task, across coding and security.

`build()` picks per task from DEV scores only (ties -> faster), records TEST scores for reporting, and
writes profiles/router.json plus results/scorecard.md. `classify()` maps a live chat request to a task.
"""
import json
import re
from pathlib import Path

from .bench import RESULTS

PROFILES = Path(__file__).resolve().parent.parent / "profiles"
TASKS = {  # task -> (benchmark key, metric)
    "coding": ("humaneval", "pass@1"),
    "security_knowledge": ("cybermetric", "accuracy"),
    "threat_intel": ("cti-mcq", "accuracy"),
    "cwe_mapping": ("cti-rcm", "accuracy"),
}
SHORT = {"hf.co/Mungert/Foundation-Sec-8B-Instruct-GGUF:Q4_K_M": "Foundation-Sec-8B"}


def _runs():
    """All summaries as {(bench, model, strategy, part): summary}. qc15:control is stock qwen2.5-coder:1.5b."""
    out = {}
    for p in RESULTS.glob("*.summary.json"):
        s = json.loads(p.read_text())
        model = "qwen2.5-coder:1.5b" if s["model"] == "qc15:control" else s["model"]
        if p.name.startswith("sec__"):
            out[(s["dataset"], model, s["strategy"], s["part"])] = s
        elif s.get("strategy") and ":" in s["model"] and not any(x in s["model"] for x in ("expo", "qc7", "qc05")):
            out[("humaneval", model, s["strategy"], s["part"])] = s
    return out


def build(think=None):
    runs = _runs()
    router, card = {}, {}
    for task, (bench, metric) in TASKS.items():
        cands = [(k, v) for k, v in runs.items() if k[0] == bench and k[3] == "dev" and v["n"] >= 40]
        cands = [(k, v) for k, v in cands if (bench, k[1], k[2], "test") in runs]
        if not cands:
            continue
        top = max(v[metric] for _, v in cands)
        n = max(v["n"] for _, v in cands)
        near = [(k, v) for k, v in cands if v[metric] >= top - 1 / n]
        (_, model, strategy, _), dev = min(near, key=lambda kv: kv[1]["avg_seconds"])
        test = runs[(bench, model, strategy, "test")]
        router[task] = {"model": model, "strategy": strategy, "dev": dev[metric], "test": test[metric],
                        "seconds": test["avg_seconds"], "think": (think or {}).get(model)}
        for (b, m, s, part), v in runs.items():
            if b == bench and part == "test":
                card.setdefault(m, {}).setdefault(task, []).append((v[metric], s))
    PROFILES.mkdir(exist_ok=True)
    (PROFILES / "router.json").write_text(json.dumps(router, indent=2))

    lines = ["# Combined scorecard (held-out test halves)", "",
             "Best measured strategy per model and task; `tvashtr/auto` routes each task to the row "
             "chosen on dev.", "",
             "| Model | Coding (HumanEval) | Security knowledge (CyberMetric) | Threat intel (CTI-MCQ) | "
             "CWE mapping (CTI-RCM) |", "|---|---|---|---|---|"]
    for m, tasks in sorted(card.items()):
        cells = []
        for task in TASKS:
            best = max(tasks.get(task, []), default=None)
            cells.append(f"{best[0]:.1%} ({best[1]})" if best else "-")
        lines.append(f"| {SHORT.get(m, m)} | " + " | ".join(cells) + " |")
    lines.append("| **tvashtr/auto** | " + " | ".join(
        f"**{router[t]['test']:.1%}** ({SHORT.get(router[t]['model'], router[t]['model'])}, {router[t]['strategy']})"
        if t in router else "-" for t in TASKS) + " |")
    (RESULTS / "scorecard.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return router


SEC_WORDS = re.compile(
    r"\b(cve|cwe|capec|att&?ck|mitre|ttps?|exploit|vulnerab\w*|malware|ransomware|phishing|threat|apt\d*|"
    r"payload|privilege escalation|lateral movement|persistence|exfiltrat\w*|c2|command and control|"
    r"pentest\w*|penetration test\w*|red team|blue team|ioc|indicator|siem|edr|xss|sqli|sql injection|csrf|ssrf|"
    r"rce|buffer overflow|mitigation|detection|incident|forensic\w*|cipher|encryption|authentication|"
    r"firewall|ids|ips|owasp|zero[- ]day|attack)\b", re.I)
CWE_ASK = re.compile(r"\b(cwe|root[- ]cause|weakness|which cwe|map (this|the) (cve|vulnerability))\b", re.I)


def classify(text, is_code_request):
    """Map a chat request to a router task."""
    if CWE_ASK.search(text) and re.search(r"\b(cve-\d{4}-\d+|vulnerabilit\w*|cve)\b", text, re.I):
        return "cwe_mapping"
    if is_code_request and not SEC_WORDS.search(text):
        return "coding"
    if SEC_WORDS.search(text):
        return "threat_intel" if re.search(r"\b(att&?ck|mitre|ttps?|apt\d*|technique|tactic|group|campaign)\b",
                                           text, re.I) else "security_knowledge"
    return "coding" if is_code_request else "general"


def load():
    p = PROFILES / "router.json"
    return json.loads(p.read_text()) if p.exists() else {}
