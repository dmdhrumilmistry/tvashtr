"""Regenerate the README charts (static SVG, light + dark) from results/*.summary.json.

    python scripts/make_charts.py            # writes docs/charts/*.svg

Palette: the dataviz reference categorical slots 1-3 (validated all-pairs in both modes). Slot 3
(aqua) is below 3:1 on the light surface, so every chart carries direct labels and the README has
a table view of the same numbers.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RES = ROOT / "results"
OUT = ROOT / "docs" / "charts"

STYLE = """<style>
  .surface{fill:#fcfcfb} .ink{fill:#0b0b0b} .ink2{fill:#52514e} .muted{fill:#898781}
  .grid{stroke:#e1e0d9;stroke-width:1} .axis{stroke:#c3c2b7;stroke-width:1}
  .s1{fill:#2a78d6} .s2{fill:#eb6834} .s3{fill:#1baf7a} .dim{fill:#c3c2b7}
  .l1{stroke:#2a78d6} .l2{stroke:#eb6834} .l3{stroke:#1baf7a} .ring{stroke:#fcfcfb}
  text{font-family:system-ui,-apple-system,"Segoe UI",sans-serif}
  .t{font-size:15px;font-weight:600} .st{font-size:12px} .lab{font-size:12px} .tick{font-size:11px;font-variant-numeric:tabular-nums}
  @media (prefers-color-scheme: dark){
    .surface{fill:#1a1a19} .ink{fill:#f0efec} .ink2{fill:#c3c2b7}
    .grid{stroke:#2c2c2a} .axis{stroke:#383835}
    .s1{fill:#3987e5} .s2{fill:#d95926} .s3{fill:#199e70} .dim{fill:#383835}
    .l1{stroke:#3987e5} .l2{stroke:#d95926} .l3{stroke:#199e70} .ring{stroke:#1a1a19}
  }
</style>"""


def summary(model, strategy, part):
    p = RES / f"{model.replace(':', '_').replace('/', '_')}__{strategy}__{part}.summary.json"
    return json.loads(p.read_text()) if p.exists() else None


def svg(w, h, body, title, subtitle):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" '
            f'role="img" aria-label="{title}">{STYLE}<rect class="surface" width="{w}" height="{h}" rx="8"/>'
            f'<text class="t ink" x="20" y="28">{title}</text><text class="st ink2" x="20" y="47">{subtitle}</text>'
            f'{body}</svg>\n')


def hbar_path(x0, y, length, h, r=4):
    """Horizontal bar anchored at x0 with a 4px rounded data end."""
    if length <= r:
        return f'M{x0},{y}h{max(length, 0.5)}v{h}h{-max(length, 0.5)}z'
    return (f'M{x0},{y}h{length - r}a{r},{r} 0 0 1 {r},{r}v{h - 2 * r}a{r},{r} 0 0 1 {-r},{r}'
            f'h{-(length - r)}z')


def vbar_path(x, base, length, w, r=4):
    """Vertical bar anchored at the baseline with a 4px rounded data end."""
    top = base - length
    if length <= r:
        return f'M{x},{base}v{-max(length, 0.5)}h{w}v{max(length, 0.5)}z'
    return (f'M{x},{base}v{-(length - r)}a{r},{r} 0 0 1 {r},{-r}h{w - 2 * r}a{r},{r} 0 0 1 {r},{r}'
            f'v{length - r}z')


def strategies_chart(model="qc15:control", label="Qwen2.5-Coder-1.5B"):
    names = {"direct": "single answer", "plan": "plan-first", "self_debug": "self-debug",
             "codet": "CodeT", "adaptive": "adaptive", "s_star": "S*"}
    rows = [(names[s], summary(model, s, "dev")) for s in names]
    rows = sorted([(n, d) for n, d in rows if d], key=lambda r: -r[1]["pass@1"])
    best = rows[0][0]
    w, left, right, top, bh, gap = 640, 120, 70, 70, 18, 10
    plot = w - left - right
    h = top + len(rows) * (bh + gap) + 40
    body = []
    for v in (0, 25, 50, 75, 100):
        x = left + plot * v / 100
        body.append(f'<line class="grid" x1="{x}" x2="{x}" y1="{top - 6}" y2="{h - 34}"/>'
                    f'<text class="tick muted" x="{x}" y="{h - 18}" text-anchor="middle">{v}%</text>')
    for i, (n, d) in enumerate(rows):
        y = top + i * (bh + gap)
        length = plot * d["pass@1"]
        cls = "s1" if n == best else "dim"
        body.append(f'<text class="lab ink" x="{left - 10}" y="{y + 13}" text-anchor="end">{n}</text>'
                    f'<path class="{cls}" d="{hbar_path(left, y, length, bh)}"/>'
                    f'<text class="lab ink" x="{left + length + 6}" y="{y + 13}">{d["pass@1"]:.1%}</text>')
    body.append(f'<line class="axis" x1="{left}" x2="{left}" y1="{top - 6}" y2="{h - 34}"/>')
    return svg(w, h, "".join(body), f"Inference-time enhancements on {label}",
               "HumanEval pass@1, dev half (82 problems). Highlighted: the strategy autotune selected.")


def cost_chart(model="qc15:control", label="Qwen2.5-Coder-1.5B"):
    names = {"direct": "single answer", "plan": "plan-first", "self_debug": "self-debug",
             "codet": "CodeT", "adaptive": "adaptive", "s_star": "S*"}
    pts = [(names[s], summary(model, s, "dev")) for s in names]
    pts = [(n, d) for n, d in pts if d]
    w, h, left, right, top, bottom = 640, 330, 60, 30, 70, 50
    pw, ph = w - left - right, h - top - bottom
    xmax = max(3000, max(d["avg_output_tokens"] for _, d in pts) * 1.1)
    ymin, ymax = 0.5, 0.9
    X = lambda v: left + pw * v / xmax
    Y = lambda v: top + ph * (1 - (v - ymin) / (ymax - ymin))
    body = []
    for v in (0.5, 0.6, 0.7, 0.8, 0.9):
        body.append(f'<line class="grid" x1="{left}" x2="{w - right}" y1="{Y(v)}" y2="{Y(v)}"/>'
                    f'<text class="tick muted" x="{left - 8}" y="{Y(v) + 4}" text-anchor="end">{v:.0%}</text>')
    for v in range(0, int(xmax) + 1, 500):
        body.append(f'<text class="tick muted" x="{X(v)}" y="{h - bottom + 18}" text-anchor="middle">{v}</text>')
    body.append(f'<line class="axis" x1="{left}" x2="{w - right}" y1="{h - bottom}" y2="{h - bottom}"/>'
                f'<text class="tick muted" x="{left + pw / 2}" y="{h - 12}" text-anchor="middle">'
                f'average output tokens per problem (cost)</text>')
    dots = [(X(d["avg_output_tokens"]), Y(d["pass@1"])) for _, d in pts]
    boxes = []  # placed label boxes (x0, y0, x1, y1)

    def clear(b):
        hits_label = any(not (b[2] < o[0] or b[0] > o[2] or b[3] < o[1] or b[1] > o[3]) for o in boxes)
        hits_dot = any(b[0] - 6 < dx < b[2] + 6 and b[1] - 6 < dy < b[3] + 6 for dx, dy in dots)
        inside = b[0] >= left and b[2] <= w - right
        return inside and not hits_label and not hits_dot

    for n, d in pts:
        x, y = X(d["avg_output_tokens"]), Y(d["pass@1"])
        text = f'{n} {d["pass@1"]:.0%}'
        tw, th = 6.6 * len(text), 12
        candidates = [("start", x + 10, y + 4), ("start", x - 4, y - 11), ("start", x - 4, y + 19),
                      ("end", x - 10, y + 4)]
        for anchor, tx, ty in candidates:
            x0 = tx if anchor == "start" else tx - tw
            box = (x0, ty - th + 2, x0 + tw, ty + 2)
            if clear(box):
                break
        boxes.append(box)
        body.append(f'<circle class="s1 ring" cx="{x}" cy="{y}" r="5" stroke-width="2"/>'
                    f'<text class="lab ink" x="{tx}" y="{ty}" text-anchor="{anchor}">{text}</text>')
    return svg(w, h, "".join(body), f"Accuracy vs cost on {label}",
               "Each point is one strategy (dev half). Up is better, right is more expensive.")


def expo_chart():
    fams = [("qc05", "0.5B", 1), ("qc15", "1.5B", 2), ("qc7", "7B", 3)]
    alphas = [0.0, 0.1, 0.3, 0.5]
    w, h, left, right, top, bottom = 640, 340, 60, 90, 70, 50
    pw, ph = w - left - right, h - top - bottom
    X = lambda a: left + pw * a / 0.5
    Y = lambda v: top + ph * (1 - v)
    body = []
    for v in (0, 0.25, 0.5, 0.75, 1.0):
        body.append(f'<line class="grid" x1="{left}" x2="{w - right}" y1="{Y(v)}" y2="{Y(v)}"/>'
                    f'<text class="tick muted" x="{left - 8}" y="{Y(v) + 4}" text-anchor="end">{v:.0%}</text>')
    for a in alphas:
        body.append(f'<text class="tick muted" x="{X(a)}" y="{h - bottom + 18}" text-anchor="middle">'
                    f'{"0 (original)" if a == 0 else a}</text>')
    body.append(f'<line class="axis" x1="{left}" x2="{w - right}" y1="{h - bottom}" y2="{h - bottom}"/>'
                f'<text class="tick muted" x="{left + pw / 2}" y="{h - 12}" text-anchor="middle">ExPO alpha</text>')
    legend_x = left
    for prefix, name, slot in fams:
        pts = []
        for a in alphas:
            d = summary(f"{prefix}:control" if a == 0 else f"{prefix}:expo-{a}", "direct", "dev")
            if d:
                pts.append((X(a), Y(d["pass@1"]), d["pass@1"]))
        if not pts:
            continue
        path = " ".join(f"{'M' if i == 0 else 'L'}{x:.1f},{y:.1f}" for i, (x, y, _) in enumerate(pts))
        body.append(f'<path class="l{slot}" d="{path}" fill="none" stroke-width="2"/>')
        body += [f'<circle class="s{slot} ring" cx="{x}" cy="{y}" r="4.5" stroke-width="2"/>' for x, y, _ in pts]
        ex, ey, ev = pts[-1]
        body.append(f'<text class="lab ink" x="{ex + 10}" y="{ey + 4}">{name} {ev:.0%}</text>')
        body.append(f'<rect class="s{slot}" x="{legend_x}" y="58" width="10" height="10" rx="2"/>'
                    f'<text class="lab ink2" x="{legend_x + 15}" y="67">Qwen2.5-Coder-{name}</text>')
        legend_x += 150
    return svg(w, h, "".join(body), "ExPO weight extrapolation: accuracy by alpha",
               "HumanEval pass@1, dev half. alpha 0 is the unmodified instruct model.")


def heldout_chart():
    rows = [("qwen3-coder:30b", "adaptive", "qwen3-coder 30B"), ("qc15:control", "s_star", "Qwen2.5-Coder 1.5B")]
    data = [(lab, summary(m, "direct", "test"), summary(m, s, "test"), s) for m, s, lab in rows]
    data = [r for r in data if r[1] and r[2]]
    w, h, left, top, bottom = 640, 320, 60, 80, 56
    pw, ph = w - left - 30, h - top - bottom
    group = pw / len(data)
    bw, gap = 46, 2
    Y = lambda v: top + ph * (1 - v)
    body = [f'<rect class="s1" x="{left}" y="58" width="10" height="10" rx="2"/>'
            f'<text class="lab ink2" x="{left + 15}" y="67">single answer</text>'
            f'<rect class="s2" x="{left + 120}" y="58" width="10" height="10" rx="2"/>'
            f'<text class="lab ink2" x="{left + 135}" y="67">best enhancement</text>']
    for v in (0, 0.25, 0.5, 0.75, 1.0):
        body.append(f'<line class="grid" x1="{left}" x2="{w - 30}" y1="{Y(v)}" y2="{Y(v)}"/>'
                    f'<text class="tick muted" x="{left - 8}" y="{Y(v) + 4}" text-anchor="end">{v:.0%}</text>')
    names = {"adaptive": "adaptive", "s_star": "S*"}
    for i, (lab, a, b, s) in enumerate(data):
        cx = left + group * i + group / 2
        x1, x2 = cx - bw - gap / 2, cx + gap / 2
        for x, d, cls in ((x1, a, "s1"), (x2, b, "s2")):
            body.append(f'<path class="{cls}" d="{vbar_path(x, Y(0), ph * d["pass@1"], bw)}"/>'
                        f'<text class="lab ink" x="{x + bw / 2}" y="{Y(d["pass@1"]) - 6}" text-anchor="middle">'
                        f'{d["pass@1"]:.1%}</text>')
        delta = round((b["pass@1"] - a["pass@1"]) * a["n"])
        body.append(f'<text class="lab ink" x="{cx}" y="{h - bottom + 18}" text-anchor="middle">{lab}</text>'
                    f'<text class="tick ink2" x="{cx}" y="{h - bottom + 34}" text-anchor="middle">'
                    f'{names[s]}: {delta:+d} problems, {b["avg_calls"]:.1f}x calls</text>')
    body.append(f'<line class="axis" x1="{left}" x2="{w - 30}" y1="{Y(0)}" y2="{Y(0)}"/>')
    return svg(w, h, "".join(body), "Held-out result: single answer vs best enhancement",
               "HumanEval pass@1 on the test half (82 problems), never used for selection.")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for name, fn in (("strategies-1.5b", strategies_chart), ("cost-vs-accuracy-1.5b", cost_chart),
                     ("expo-sweep", expo_chart), ("heldout", heldout_chart)):
        (OUT / f"{name}.svg").write_text(fn(), encoding="utf-8")
        print(f"wrote docs/charts/{name}.svg")


if __name__ == "__main__":
    main()
