"""Minimal Ollama client with token accounting. No SDK dependency."""
import os
import re
import threading

import requests

THINK_RE = re.compile(r"<think>.*?</think>\s*", re.S)


def host():
    h = os.environ.get("TVASHTR_UPSTREAM") or os.environ.get("OLLAMA_HOST") or "http://127.0.0.1:11434"
    if not h.startswith("http"):
        h = "http://" + h
    return h.rstrip("/")


class Usage:
    """Thread-safe counter of model calls and tokens, so every strategy reports its real cost."""

    def __init__(self):
        self.calls = self.prompt_tokens = self.output_tokens = 0
        self._lock = threading.Lock()

    def add(self, resp):
        with self._lock:
            self.calls += 1
            self.prompt_tokens += resp.get("prompt_eval_count", 0) or 0
            self.output_tokens += resp.get("eval_count", 0) or 0

    def as_dict(self):
        return {"calls": self.calls, "prompt_tokens": self.prompt_tokens, "output_tokens": self.output_tokens}


class LLM:
    def __init__(self, model, usage=None, num_ctx=8192, timeout=600, upstream=None):
        self.model, self.num_ctx, self.timeout = model, num_ctx, timeout
        self.usage = usage or Usage()
        self.base = (upstream or host()).rstrip("/")

    def chat(self, messages, temperature=0.0, max_tokens=2048, seed=None, stop=None):
        opts = {"temperature": temperature, "num_ctx": self.num_ctx, "num_predict": max_tokens}
        if seed is not None:
            opts["seed"] = seed
        if stop:
            opts["stop"] = stop
        r = requests.post(f"{self.base}/api/chat", timeout=self.timeout, json={
            "model": self.model, "messages": messages, "stream": False, "options": opts,
        })
        r.raise_for_status()
        data = r.json()
        self.usage.add(data)
        return THINK_RE.sub("", data["message"].get("content", ""))

    def ask(self, prompt, system=None, **kw):
        msgs = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": prompt}]
        return self.chat(msgs, **kw)
