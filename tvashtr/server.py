"""Ollama-compatible endpoint that applies post-training enhancements to `tvashtr/<model>` requests.

Point any Ollama or OpenAI-compatible client (Continue, Aider, Open WebUI, Cline) at
http://127.0.0.1:11435 and pick a `tvashtr/...` model. Self-contained Python code-writing requests
go through the model's tuned strategy (profiles/<model>.json, default `adaptive`). Everything else -
tool/agent calls, FIM autocomplete, explanations, other languages, plain model names - is proxied to
Ollama unchanged, so nothing breaks.
"""
import json
import re
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import requests

import os

from . import router, sandbox, secbench
from .bench import docstring_tests
from .llm import LLM, host
from .strategies import STRATEGIES, Task

PREFIX = "tvashtr/"
AUTO = "tvashtr/auto"  # routes each request to the measured best model + strategy for its task
PROFILES = Path(__file__).resolve().parent.parent / "profiles"
OTHER_LANG = re.compile(r"\b(javascript|typescript|node\.?js|java|c\+\+|c#|golang|rust|ruby|php|swift|kotlin|"
                        r"bash|shell script|powershell|sql|html|css|react|vue|scala|haskell|lua|dart)\b", re.I)
CODE_ASK = re.compile(r"\b(write|implement|create|build|complete|fix|code|refactor|solve)\b", re.I)
CODE_NOUN = re.compile(r"\b(function|def|class|script|program|algorithm|method|code|solution)\b|```", re.I)
EXPLAIN = re.compile(r"^\s*(why|what|explain|how does|how do|review|compare|describe)\b", re.I)


def profile(model):
    p = PROFILES / f"{model.replace(':', '_').replace('/', '_')}.json"
    if p.exists():
        d = json.loads(p.read_text())
        return d["strategy"], d.get("params", {})
    return "adaptive", {}


def should_enhance(body):
    if body.get("tools") or body.get("format") or not body.get("messages"):
        return False
    last = body["messages"][-1]
    text = last.get("content") if isinstance(last.get("content"), str) else ""
    if last.get("role") != "user" or last.get("images") or not text:
        return False
    if OTHER_LANG.search(text) and not re.search(r"\bpython\b", text, re.I):
        return False
    return bool(CODE_ASK.search(text) and CODE_NOUN.search(text) and not EXPLAIN.match(text))


def build_task(messages):
    text = messages[-1]["content"]
    history = [m for m in messages[:-1] if m.get("role") in ("user", "assistant") and m.get("content")]
    context = "".join(f"{m['role'].upper()}: {m['content']}\n\n" for m in history[-6:])
    prompt = (f"Conversation so far:\n\n{context}Current request:\n\n{text}" if context else text)
    system = next((m["content"] for m in messages if m.get("role") == "system"), None)
    if system:
        prompt = f"{system}\n\n{prompt}"
    defs = re.findall(r"def\s+([A-Za-z_]\w*)\s*\(", text)
    entry = defs[-1] if defs else None
    prelude = []
    for block in sandbox.CODE_BLOCK.findall(text):
        try:
            compile(block, "<user>", "exec")
            prelude.append(block)
        except SyntaxError:
            pass
    tests = re.findall(r"^\s*(assert .+)$", text, re.M) + (docstring_tests(text, entry) if entry else [])
    return Task(prompt, entry, list(dict.fromkeys(tests)), "\n".join(prelude))


def enhance(model, body, strategy=None):
    prof_strategy, params = profile(model)
    strategy = strategy or prof_strategy
    opts = body.get("options") or {}
    llm = LLM(model, num_ctx=opts.get("num_ctx", 8192))
    t0 = time.time()
    out = STRATEGIES[strategy](llm, build_task(body["messages"]), **params)
    content = f"```python\n{out.code}```"
    meta = {"strategy": strategy, "trace": out.trace, **llm.usage.as_dict(), "seconds": round(time.time() - t0, 1)}
    return content, meta


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        print(f"[tvashtr] {self.command} {self.path} {fmt % args}")

    # ------------------------------------------------------------------ plumbing
    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(n) if n else b""

    def _send_json(self, obj, status=200):
        data = json.dumps(obj).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _start_chunked(self, ctype):
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Transfer-Encoding", "chunked")
        self.end_headers()

    def _chunk(self, data):
        if isinstance(data, str):
            data = data.encode()
        self.wfile.write(f"{len(data):X}\r\n".encode() + data + b"\r\n")
        self.wfile.flush()

    def _proxy(self, raw):
        up = requests.request(self.command, host() + self.path, data=raw or None, stream=True, timeout=3600,
                              headers={k: v for k, v in self.headers.items()
                                       if k.lower() not in ("host", "content-length", "connection")})
        self.send_response(up.status_code)
        self.send_header("Content-Type", up.headers.get("Content-Type", "application/json"))
        self.send_header("Transfer-Encoding", "chunked")
        self.end_headers()
        for part in up.iter_content(chunk_size=None):
            if part:
                self._chunk(part)
        self._chunk(b"")

    # ------------------------------------------------------------------ routes
    def do_GET(self):
        if self.path.rstrip("/") in ("/api/tags", "/v1/models"):
            tags = requests.get(host() + "/api/tags", timeout=30).json()
            models = tags.get("models", [])
            enhanced = [{**m, "name": PREFIX + m["name"], "model": PREFIX + m["model"]} for m in models]
            if models:
                enhanced.insert(0, {**models[0], "name": AUTO, "model": AUTO})
            if self.path.startswith("/v1"):
                return self._send_json({"object": "list", "data": [
                    {"id": m["name"], "object": "model", "owned_by": "tvashtr"} for m in models + enhanced]})
            return self._send_json({"models": models + enhanced})
        self._proxy(None)

    def do_DELETE(self):
        self._proxy(self._body())

    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_POST(self):
        raw = self._body()
        try:
            body = json.loads(raw or b"{}")
        except ValueError:
            return self._proxy(raw)
        model = body.get("model", "")
        if model == AUTO and (self.path.startswith("/api/chat") or self.path.startswith("/v1/chat/completions")):
            return self._route(body)
        if not model.startswith(PREFIX):
            return self._proxy(raw)
        base = model[len(PREFIX):]
        body["model"] = base
        openai = self.path.startswith("/v1/chat/completions")
        if self.path.startswith("/api/chat") or openai:
            if should_enhance(body):
                return self._respond_enhanced(model, base, body, openai)
        self._proxy(json.dumps(body).encode())

    def _route(self, body):
        """tvashtr/auto: classify the request, then use the task's measured best model + strategy."""
        routes = router.load()
        msgs = body.get("messages") or [{}]
        text = msgs[-1].get("content") if isinstance(msgs[-1].get("content"), str) else ""
        task = router.classify(text, should_enhance(body))
        cfg = routes.get(task) or routes.get("coding") or {}
        target = cfg.get("model") or os.environ.get("TVASHTR_DEFAULT_MODEL", "qwen3:14b")
        strategy = cfg.get("strategy", "direct")
        body = {**body, "model": target}
        if cfg.get("think") is not None and "think" not in body:
            body["think"] = cfg["think"]
        print(f"[tvashtr] auto -> {task}: {target} ({strategy})")
        openai = self.path.startswith("/v1/chat/completions")
        if task == "coding" and strategy in STRATEGIES and strategy != "direct" and should_enhance(body):
            return self._respond_enhanced(AUTO, target, body, openai, strategy)
        if task in ("cwe_mapping", "threat_intel", "security_knowledge") and strategy.startswith("rag") and text:
            item = {"kind": "rcm" if task == "cwe_mapping" else "mcq", "question": text, "options": {}}
            hyp = secbench.hypothesis(LLM(target, think=cfg.get("think")), item) if strategy == "rag_hyde" else ""
            ctx = secbench.context(item, hyp)
            note = ("Use the reference material below when it is relevant; it comes from the public MITRE "
                    "knowledge bases. Prefer the most specific CWE or technique and cite its ID.\n\n" + ctx)
            body["messages"] = [{"role": "system", "content": note}] + list(msgs)
        elif strategy in ("cot", "rag_cot") or (strategy == "sc5" and task != "coding"):
            body["messages"] = [{"role": "system", "content": "Reason step by step before giving the final answer."}] \
                + list(msgs)
        return self._proxy(json.dumps(body).encode())

    def _respond_enhanced(self, alias, base, body, openai, strategy=None):
        try:
            content, meta = enhance(base, body, strategy)
        except Exception as e:  # fall back to the plain model rather than failing the client
            print(f"[tvashtr] enhancement failed ({e}); passing through")
            return self._proxy(json.dumps(body).encode())
        print(f"[tvashtr] {alias}: {json.dumps(meta)}")
        stream = body.get("stream", not openai)
        now = int(time.time())
        if openai:
            msg = {"role": "assistant", "content": content}
            if not stream:
                return self._send_json({"id": f"tvashtr-{now}", "object": "chat.completion", "created": now,
                                        "model": alias, "choices": [{"index": 0, "message": msg,
                                                                     "finish_reason": "stop"}]})
            self._start_chunked("text/event-stream")
            for delta, fin in (({"role": "assistant", "content": content}, None), ({}, "stop")):
                self._chunk("data: " + json.dumps({"id": f"tvashtr-{now}", "object": "chat.completion.chunk",
                                                   "created": now, "model": alias, "choices": [
                                                       {"index": 0, "delta": delta, "finish_reason": fin}]}) + "\n\n")
            self._chunk("data: [DONE]\n\n")
            return self._chunk(b"")
        msg = {"role": "assistant", "content": content}
        created = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        final = {"model": alias, "created_at": created, "message": msg, "done": True, "done_reason": "stop",
                 "eval_count": meta["output_tokens"], "prompt_eval_count": meta["prompt_tokens"]}
        if not stream:
            return self._send_json(final)
        self._start_chunked("application/x-ndjson")
        self._chunk(json.dumps({"model": alias, "created_at": created, "message": msg, "done": False}) + "\n")
        self._chunk(json.dumps({**final, "message": {"role": "assistant", "content": ""}}) + "\n")
        self._chunk(b"")


def serve(bind="127.0.0.1", port=11435):
    srv = ThreadingHTTPServer((bind, port), Handler)
    srv.daemon_threads = True
    print(f"tvashtr listening on http://{bind}:{port} (upstream {host()}); use models named {PREFIX}<model>")
    srv.serve_forever()
