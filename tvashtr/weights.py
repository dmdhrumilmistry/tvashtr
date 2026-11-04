"""Training-free weight updates.

ExPO (Zheng et al. 2024, "Weak-to-Strong Extrapolation Expedites Alignment"):
    theta = theta_instruct + alpha * (theta_instruct - theta_base)
Task arithmetic (Ilharco et al. 2023) for optional same-family donors:
    theta += beta_i * (theta_donor_i - theta_base)

Streams safetensors through numpy in chunks: no GPU, no torch, a few GB of RAM even for 7B models.
"""
import json
import os
import re
import shutil
import struct
import subprocess
from pathlib import Path

import numpy as np

CHUNK = 1 << 24  # elements per chunk (64 MB of float32)


def _header(path):
    with open(path, "rb") as f:
        n = struct.unpack("<Q", f.read(8))[0]
        return 8 + n, json.loads(f.read(n))


class Shards:
    """Name -> tensor lookup across a (possibly sharded) safetensors checkpoint."""

    def __init__(self, d):
        self.dir = Path(d)
        files = sorted(self.dir.glob("*.safetensors"))
        if not files:
            raise SystemExit(f"No .safetensors files in {d}")
        self.where = {}
        for f in files:
            off, hdr = _header(f)
            for name, meta in hdr.items():
                if name != "__metadata__":
                    self.where[name] = (f, off, meta)

    def flat(self, name):
        f, off, meta = self.where[name]
        start, end = meta["data_offsets"]
        raw = np.memmap(f, dtype=np.uint8, mode="r", offset=off + start, shape=(end - start,))
        return meta["dtype"], raw


def _to_f32(dtype, raw, a, b):
    if dtype == "BF16":
        u = raw.view(np.uint16)[a:b].astype(np.uint32) << 16
        return u.view(np.float32)
    if dtype == "F16":
        return raw.view(np.float16)[a:b].astype(np.float32)
    if dtype == "F32":
        return np.array(raw.view(np.float32)[a:b])
    raise ValueError(f"unsupported dtype {dtype}")


def _from_f32(x, dtype):
    if dtype == "BF16":  # round to nearest even
        u = x.view(np.uint32)
        return ((u + 0x7FFF + ((u >> 16) & 1)) >> 16).astype(np.uint16).tobytes()
    if dtype == "F16":
        return x.astype(np.float16).tobytes()
    return x.astype(np.float32).tobytes()


def _numel(meta):
    n = 1
    for s in meta["shape"]:
        n *= s
    return n


def expo(base_dir, instruct_dir, out_dir, alpha, donors=(), exclude=None):
    base, inst = Shards(base_dir), Shards(instruct_dir)
    donor_shards = [(Shards(d), beta) for d, beta in donors]
    skip = re.compile(exclude) if exclude else None
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    for f in Path(instruct_dir).iterdir():  # config, tokenizer, generation config, licence, index
        if f.is_file() and f.suffix != ".safetensors":
            shutil.copy2(f, out / f.name)

    by_file = {}
    for name, (f, _, meta) in inst.where.items():
        by_file.setdefault(f.name, []).append((name, meta))
    changed = kept = 0
    for fname, tensors in sorted(by_file.items()):
        header, pos = {"__metadata__": {"format": "pt", "tvashtr": f"expo alpha={alpha}"}}, 0
        for name, meta in tensors:
            size = meta["data_offsets"][1] - meta["data_offsets"][0]
            header[name] = {"dtype": meta["dtype"], "shape": meta["shape"], "data_offsets": [pos, pos + size]}
            pos += size
        hb = json.dumps(header, separators=(",", ":")).encode()
        hb += b" " * (-len(hb) % 8)
        with open(out / fname, "wb") as fo:
            fo.write(struct.pack("<Q", len(hb)) + hb)
            for name, meta in tensors:
                dt, raw_i = inst.flat(name)
                compatible = (name in base.where and base.where[name][2]["shape"] == meta["shape"]
                              and not (skip and skip.search(name)))
                if not compatible:
                    fo.write(raw_i.tobytes())
                    kept += 1
                    continue
                dt_b, raw_b = base.flat(name)
                n = _numel(meta)
                for a in range(0, n, CHUNK):
                    b = min(n, a + CHUNK)
                    ti, tb = _to_f32(dt, raw_i, a, b), _to_f32(dt_b, raw_b, a, b)
                    res = ti + alpha * (ti - tb)
                    for ds, beta in donor_shards:
                        if name in ds.where:
                            dd, rd = ds.flat(name)
                            res += beta * (_to_f32(dd, rd, a, b) - tb)
                    fo.write(_from_f32(res, dt))
                changed += 1
        print(f"wrote {fname}")
    print(f"ExPO alpha={alpha}: {changed} tensors extrapolated, {kept} copied unchanged -> {out}")
    return out


QWEN_TEMPLATE = '''TEMPLATE """{{- if .Suffix }}<|fim_prefix|>{{ .Prompt }}<|fim_suffix|>{{ .Suffix }}<|fim_middle|>
{{- else if .Messages }}
{{- if or .System .Tools }}<|im_start|>system
{{- if .System }}
{{ .System }}
{{- else }}
You are a helpful coding assistant.
{{- end }}
{{- if .Tools }}

# Tools

You may call one or more functions to assist with the user query.

You are provided with function signatures within <tools></tools> XML tags:
<tools>
{{- range .Tools }}
{"type": "function", "function": {{ .Function }}}
{{- end }}
</tools>

For each function call, return a json object with function name and arguments within <tool_call></tool_call> XML tags:
<tool_call>
{"name": <function-name>, "arguments": <args-json-object>}
</tool_call>
{{- end }}<|im_end|>
{{ end }}
{{- range $i, $_ := .Messages }}
{{- $last := eq (len (slice $.Messages $i)) 1 -}}
{{- if eq .Role "user" }}<|im_start|>user
{{ .Content }}<|im_end|>
{{ else if eq .Role "assistant" }}<|im_start|>assistant
{{ if .Content }}{{ .Content }}
{{- else if .ToolCalls }}<tool_call>
{{ range .ToolCalls }}{"name": "{{ .Function.Name }}", "arguments": {{ .Function.Arguments }}}
{{ end }}</tool_call>
{{- end }}{{ if not $last }}<|im_end|>
{{ end }}
{{- else if eq .Role "tool" }}<|im_start|>user
<tool_response>
{{ .Content }}
</tool_response><|im_end|>
{{ end }}
{{- if and (ne .Role "assistant") $last }}<|im_start|>assistant
{{ end }}
{{- end }}
{{- else }}
{{- if .System }}<|im_start|>system
{{ .System }}<|im_end|>
{{ end }}<|im_start|>user
{{ .Prompt }}<|im_end|>
<|im_start|>assistant
{{ end }}"""
PARAMETER stop "<|im_start|>"
PARAMETER stop "<|im_end|>"
PARAMETER stop "<|endoftext|>"
'''


def ollama_import(model_dir, name, quantize="int8", num_ctx=8192):
    """`ollama create` straight from safetensors (Ollama quantizes on import). Honours OLLAMA_HOST.

    Note: recent Ollama builds route safetensors imports through the MLX engine, which rejects some
    architectures (e.g. Qwen2). Use the GGUF path (`expo-gguf`) for those.
    """
    mf = Path(model_dir) / "Modelfile"
    mf.write_text(f"FROM .\n{QWEN_TEMPLATE}PARAMETER num_ctx {num_ctx}\n", encoding="utf-8")
    cmd = ["ollama", "create", name, "-f", str(mf)] + (["--quantize", quantize] if quantize else [])
    subprocess.run(cmd, check=True, cwd=model_dir, env=os.environ.copy())


# ---------------------------------------------------------------------------- GGUF path
# Works on the fp16 GGUF builds Ollama already serves (e.g. qwen2.5-coder:7b-base-fp16 and
# :7b-instruct-fp16), so no converter, torch or llama.cpp is needed. The instruct file's header
# (tokenizer, chat template, tensor layout) is copied byte for byte; only tensor data changes.

GGUF_SCALAR = {0: 1, 1: 1, 2: 2, 3: 2, 4: 4, 5: 4, 6: 4, 7: 1, 10: 8, 11: 8, 12: 8}
GGML_FLOAT = {0: np.float32, 1: np.float16}  # F32, F16
GGML_BF16 = 30


class GGUF:
    def __init__(self, path):
        self.path = Path(path)
        with open(self.path, "rb") as f:
            assert f.read(4) == b"GGUF", f"{path} is not a GGUF file"
            self.version, n_tensors, n_kv = struct.unpack("<IQQ", f.read(20))
            self.kv = {}
            for _ in range(n_kv):
                key = self._str(f)
                vtype = struct.unpack("<I", f.read(4))[0]
                self.kv[key] = self._val(f, vtype)
            self.tensors = {}
            for _ in range(n_tensors):
                name = self._str(f)
                nd = struct.unpack("<I", f.read(4))[0]
                dims = struct.unpack(f"<{nd}Q", f.read(8 * nd))
                gtype, off = struct.unpack("<IQ", f.read(12))
                self.tensors[name] = (gtype, dims, off)
            align = int(self.kv.get("general.alignment", 32))
            pos = f.tell()
            self.data_start = pos + (-pos % align)

    @staticmethod
    def _str(f):
        n = struct.unpack("<Q", f.read(8))[0]
        return f.read(n).decode("utf-8", errors="replace")

    def _val(self, f, t):
        if t == 8:
            return self._str(f)
        if t == 9:
            et, n = struct.unpack("<IQ", f.read(12))
            if et == 8:
                return [self._str(f) for _ in range(n)]
            f.seek(GGUF_SCALAR[et] * n, 1)  # large numeric arrays (token scores/types) are skipped
            return f"<array {n}>"
        raw = f.read(GGUF_SCALAR[t])
        return struct.unpack({0: "<B", 1: "<b", 2: "<H", 3: "<h", 4: "<I", 5: "<i", 6: "<f", 7: "<?",
                              10: "<Q", 11: "<q", 12: "<d"}[t], raw)[0]

    def array(self, name):
        gtype, dims, off = self.tensors[name]
        n = int(np.prod(dims)) if dims else 1
        if gtype in GGML_FLOAT:
            return np.memmap(self.path, dtype=GGML_FLOAT[gtype], mode="r", offset=self.data_start + off, shape=(n,))
        if gtype == GGML_BF16:
            return np.memmap(self.path, dtype=np.uint16, mode="r", offset=self.data_start + off, shape=(n,))
        raise SystemExit(f"tensor {name} is quantized (ggml type {gtype}); use fp16/bf16 GGUF builds")


def _f32(arr, gtype, a, b):
    x = arr[a:b]
    return (x.astype(np.uint32) << 16).view(np.float32) if gtype == GGML_BF16 else x.astype(np.float32)


def _back(x, gtype):
    if gtype == GGML_BF16:
        u = x.view(np.uint32)
        return ((u + 0x7FFF + ((u >> 16) & 1)) >> 16).astype(np.uint16)
    return x.astype(GGML_FLOAT[gtype])


def expo_gguf(base_path, instruct_path, out_path, alpha, donors=(), exclude=None):
    base, inst = GGUF(base_path), GGUF(instruct_path)
    donor_files = [(GGUF(p), beta) for p, beta in donors]
    skip = re.compile(exclude) if exclude else None
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(inst.path, "rb") as fi, open(out, "wb") as fo:
        fo.write(fi.read(inst.data_start))
    changed = 0
    with open(out, "r+b") as fo:
        for name, (gtype, dims, off) in inst.tensors.items():
            src = inst.array(name)
            n = src.shape[0]
            fo.seek(inst.data_start + off)
            same = (name in base.tensors and base.tensors[name][:2] == (gtype, dims)
                    and not (skip and skip.search(name)))
            if not same:
                fo.write(np.asarray(src).tobytes())
                continue
            bsrc = base.array(name)
            for a in range(0, n, CHUNK):
                b = min(n, a + CHUNK)
                ti, tb = _f32(src, gtype, a, b), _f32(bsrc, gtype, a, b)
                res = ti + alpha * (ti - tb)
                for d, beta in donor_files:
                    if name in d.tensors and d.tensors[name][:2] == (gtype, dims):
                        res += beta * (_f32(d.array(name), gtype, a, b) - tb)
                fo.write(_back(res, gtype).tobytes())
            changed += 1
    print(f"ExPO alpha={alpha}: {changed}/{len(inst.tensors)} tensors extrapolated -> {out}")
    return out


def ollama_blob(model, models_dir=None):
    """Path of the GGUF weights blob behind an Ollama model tag (reads `ollama show --modelfile`)."""
    text = subprocess.run(["ollama", "show", model, "--modelfile"], capture_output=True, text=True,
                          check=True, env=os.environ.copy()).stdout
    m = re.search(r"^FROM\s+(\S+sha256-[0-9a-f]+)\s*$", text, re.M)
    if not m:
        raise SystemExit(f"could not locate the weights blob for {model}")
    return Path(m.group(1))


def ollama_create_gguf(gguf, name, template_from=None, quantize=None, num_ctx=8192, modelfile_dir=None):
    """Register a GGUF with Ollama, reusing the source model's chat template when given."""
    tmpl = QWEN_TEMPLATE
    if template_from:
        shown = subprocess.run(["ollama", "show", template_from, "--modelfile"], capture_output=True,
                               text=True, env=os.environ.copy()).stdout
        t = re.search(r'^TEMPLATE\s+""".*?"""', shown, re.S | re.M)
        stops = re.findall(r"^PARAMETER stop .*$", shown, re.M)
        if t:
            tmpl = t.group(0) + "\n" + "\n".join(stops) + "\n"
    mf_dir = Path(modelfile_dir) if modelfile_dir else Path(gguf).parent
    mf_dir.mkdir(parents=True, exist_ok=True)
    mf = mf_dir / (re.sub(r"[^\w.-]", "_", name) + ".Modelfile")
    mf.write_text(f"FROM {Path(gguf).resolve()}\n{tmpl}PARAMETER num_ctx {num_ctx}\n", encoding="utf-8")
    cmd = ["ollama", "create", name, "-f", str(mf)] + (["--quantize", quantize] if quantize else [])
    subprocess.run(cmd, check=True, env=os.environ.copy())
