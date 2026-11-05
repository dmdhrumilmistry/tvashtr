"""Public security knowledge bases (MITRE CWE, CAPEC, ATT&CK Enterprise) with a pure-Python BM25 index.

Downloaded on first use from MITRE and cached under data/kb/. Only these public catalogues are
indexed, never benchmark data.
"""
import io
import json
import math
import pickle
import re
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

from .bench import DATA

KB = DATA / "kb"
URLS = {
    "cwe": "https://cwe.mitre.org/data/xml/cwec_latest.xml.zip",
    "capec": "https://capec.mitre.org/data/xml/capec_latest.xml",
    "attack": "https://raw.githubusercontent.com/mitre-attack/attack-stix-data/master/enterprise-attack/enterprise-attack.json",
}
STOP = set("a an and are as at be by for from has have in is it its of on or that the this to was were which "
           "with not can may via such when where who will into than then these those also".split())
TOKEN = re.compile(r"[a-z0-9]+")  # split on punctuation so "use-after-free" == "Use After Free"


def tokens(text):
    return [t for t in TOKEN.findall((text or "").lower()) if t not in STOP and len(t) > 1]


def _get(name):
    KB.mkdir(parents=True, exist_ok=True)
    path = KB / Path(URLS[name]).name
    if not path.exists():
        req = urllib.request.Request(URLS[name], headers={"User-Agent": "tvashtr-kb"})
        with urllib.request.urlopen(req, timeout=300) as r, open(path, "wb") as f:
            f.write(r.read())
    return path


def _text(el):
    return " ".join(" ".join(el.itertext()).split()) if el is not None else ""


def _xml_root(path):
    if path.suffix == ".zip":
        with zipfile.ZipFile(path) as z:
            data = z.read([n for n in z.namelist() if n.endswith(".xml")][0])
        return ET.parse(io.BytesIO(data)).getroot()
    return ET.parse(path).getroot()


def _strip_ns(root):
    for el in root.iter():
        if isinstance(el.tag, str) and "}" in el.tag:
            el.tag = el.tag.split("}", 1)[1]
    return root


def load_cwe():
    root = _strip_ns(_xml_root(_get("cwe")))
    docs, views = [], defaultdict(set)
    for w in root.iter("Weakness"):
        if w.get("Status") == "Deprecated":
            continue
        cid = f"CWE-{w.get('ID')}"
        alt = " ".join(_text(t.find("Term")) for t in w.iter("Alternate_Term"))
        # observed examples are real CVE descriptions MITRE mapped to this CWE: the best match signal
        examples = [(_text(o.find("Reference")), _text(o.find("Description"))) for o in w.iter("Observed_Example")]
        ex = " ".join(d for _, d in examples)[:1500]
        docs.append({"id": cid, "source": "cwe", "title": f"{cid}: {w.get('Name')}",
                     "text": f"{_text(w.find('Description'))} {_text(w.find('Extended_Description'))[:600]}",
                     "extra": f"{alt} {ex}", "cves": [r for r, _ in examples]})
    for c in root.iter("Category"):
        if c.get("Status") == "Deprecated":
            continue
        cid = f"CWE-{c.get('ID')}"
        docs.append({"id": cid, "source": "cwe", "title": f"{cid}: {c.get('Name')} (category)",
                     "text": _text(c.find("Summary"))[:800], "extra": ""})
    # graph views (e.g. NVD's CWE-1003) attach children through view-scoped ChildOf relationships
    for w in root.iter("Weakness"):
        for rel in w.iter("Related_Weakness"):
            if rel.get("View_ID"):
                views[rel.get("View_ID")].add(f"CWE-{w.get('ID')}")
    members = defaultdict(set)  # category -> members (categories nest)
    for c in root.iter("Category"):
        for m in c.iter("Has_Member"):
            members[f"CWE-{c.get('ID')}"].add(f"CWE-{m.get('CWE_ID')}")
    for v in root.iter("View"):
        todo = [f"CWE-{m.get('CWE_ID')}" for m in v.iter("Has_Member")]
        while todo:
            cid = todo.pop()
            if cid in views[v.get("ID")]:
                continue
            views[v.get("ID")].add(cid)
            todo.extend(members.get(cid, ()))
    return docs, {k: sorted(v) for k, v in views.items()}


def load_capec():
    root = _strip_ns(_xml_root(_get("capec")))
    docs = []
    for a in root.iter("Attack_Pattern"):
        if a.get("Status") == "Deprecated":
            continue
        cid = f"CAPEC-{a.get('ID')}"
        cwes = " ".join(f"CWE-{r.get('CWE_ID')}" for r in a.iter("Related_Weakness"))
        mit = " ".join(_text(m) for m in a.iter("Mitigation"))[:600]
        docs.append({"id": cid, "source": "capec", "title": f"{cid}: {a.get('Name')}",
                     "text": f"{_text(a.find('Description'))} {_text(a.find('Extended_Description'))[:600]} "
                             f"Mitigations: {mit} Related weaknesses: {cwes}", "extra": ""})
    return docs


def load_attack():
    objs = json.loads(_get("attack").read_text(encoding="utf-8"))["objects"]
    live = {o["id"]: o for o in objs if not o.get("revoked") and not o.get("x_mitre_deprecated")}

    def ext_id(o):
        return next((r["external_id"] for r in o.get("external_references", [])
                     if r.get("source_name") == "mitre-attack"), None)

    mitigations, users = defaultdict(list), defaultdict(list)
    for o in live.values():
        if o.get("type") != "relationship":
            continue
        src, dst = live.get(o.get("source_ref")), live.get(o.get("target_ref"))
        if not src or not dst:
            continue
        if o["relationship_type"] == "mitigates":
            mitigations[dst["id"]].append(src["name"])
        elif o["relationship_type"] == "uses" and dst.get("type") == "attack-pattern":
            users[dst["id"]].append(src["name"])
    docs = []
    kinds = {"attack-pattern": "technique", "course-of-action": "mitigation", "intrusion-set": "group",
             "malware": "software", "tool": "software", "x-mitre-tactic": "tactic"}
    for o in live.values():
        kind = kinds.get(o.get("type"))
        if not kind:
            continue
        eid = ext_id(o) or o["id"]
        extra = ""
        if kind == "technique":
            tactics = ", ".join(p["phase_name"] for p in o.get("kill_chain_phases", []))
            extra = (f"Tactics: {tactics}. Platforms: {', '.join(o.get('x_mitre_platforms', []))}. "
                     f"Mitigations: {', '.join(sorted(set(mitigations[o['id']])))}. "
                     f"Used by: {', '.join(sorted(set(users[o['id']]))[:25])}. "
                     f"Detection: {(o.get('x_mitre_detection') or '')[:400]}")
        elif kind in ("group", "software"):
            extra = f"Aliases: {', '.join(o.get('aliases', o.get('x_mitre_aliases', [])) or [])}"
        docs.append({"id": eid, "source": "attack", "title": f"{eid}: {o['name']} ({kind})",
                     "text": (o.get("description") or "")[:1200], "extra": extra})
    return docs


class Index:
    """BM25F-style: each field gets its own length normalisation and weight, so a precise name is not
    drowned out by long example text. Fields: name (title + alternate terms), desc, examples."""

    FIELDS = {"name": 3.0, "desc": 1.0, "ex": 0.6}

    def __init__(self, docs, k1=1.2, b=0.75):
        self.docs, self.k1, self.b = docs, k1, b
        self.tf = {f: [] for f in self.FIELDS}
        self.len = {f: [] for f in self.FIELDS}
        df = Counter()
        for d in docs:
            extra = d.get("extra", "")
            fields = {"name": d["title"], "desc": d["text"], "ex": extra}
            if d["source"] == "cwe":  # alternate terms (the first chunk of `extra`) belong with the name
                fields["name"] = f"{d['title']} {extra[:120]}"
            seen = set()
            for f, text in fields.items():
                c = Counter(tokens(text))
                self.tf[f].append(c)
                self.len[f].append(sum(c.values()))
                seen |= c.keys()
            df.update(seen)
        n = len(docs)
        self.avg = {f: sum(v) / max(n, 1) or 1 for f, v in self.len.items()}
        self.idf = {t: math.log(1 + (n - c + 0.5) / (c + 0.5)) for t, c in df.items()}
        self.post = defaultdict(set)
        for f in self.FIELDS:
            for i, c in enumerate(self.tf[f]):
                for t in c:
                    self.post[t].add(i)

    def search(self, query, k=8, sources=None, allow=None):
        q = Counter(tokens(query))
        scores = defaultdict(float)
        for t in q:
            idf = self.idf.get(t)
            if not idf:
                continue
            for i in self.post[t]:
                # combine field-normalised term frequency, then saturate once (BM25F)
                tf = sum(w * self.tf[f][i].get(t, 0) / (1 - self.b + self.b * self.len[f][i] / self.avg[f])
                         for f, w in self.FIELDS.items())
                scores[i] += idf * tf * (self.k1 + 1) / (tf + self.k1)
        ranked = sorted(scores.items(), key=lambda kv: -kv[1])
        out = []
        for i, s in ranked:
            d = self.docs[i]
            if (sources and d["source"] not in sources) or (allow and d["id"] not in allow):
                continue
            out.append({**d, "score": round(s, 3)})
            if len(out) >= k:
                break
        return out


_CACHE = {}


def get():
    """(index, cwe_views); built once and cached on disk."""
    if "kb" in _CACHE:
        return _CACHE["kb"]
    pkl = KB / "index.pkl"
    if pkl.exists():
        _CACHE["kb"] = pickle.loads(pkl.read_bytes())
        return _CACHE["kb"]
    cwe_docs, views = load_cwe()
    docs = cwe_docs + load_capec() + load_attack()
    kb = (Index(docs), views)
    KB.mkdir(parents=True, exist_ok=True)
    pkl.write_bytes(pickle.dumps(kb))
    _CACHE["kb"] = kb
    return kb


def fmt(docs, max_chars=500):
    return "\n".join(f"- {d['title']}: {(d['text'] + ' ' + d.get('extra', '')).strip()[:max_chars]}" for d in docs)
