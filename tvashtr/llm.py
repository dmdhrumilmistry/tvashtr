"""Minimal Ollama client with token accounting. No SDK dependency."""
import os
import re
import threading
import time

import requests

THINK_RE = re.compile(r"<think>.*?</think>\s*", re.S)
RETRIES = 4
BACKOFF = (2, 5, 10, 20)


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
    def __init__(self, model, usage=None, num_ctx=8192, timeout=600, upstream=None, think=None):
        """`think`: None = model default; False/True or "low"/"medium"/"high" for reasoning models.

        TVASHTR_THINK sets the default (e.g. `false` to answer directly, `low` for gpt-oss)."""
        self.model, self.num_ctx, self.timeout = model, num_ctx, timeout
        self.usage = usage or Usage()
        self.base = (upstream or host()).rstrip("/")
        env = os.environ.get("TVASHTR_THINK")
        if think is None and env:
            think = {"false": False, "true": True}.get(env.lower(), env.lower())
        self.think = think

    def chat(self, messages, temperature=0.0, max_tokens=2048, seed=None, stop=None):
        opts = {"temperature": temperature, "num_ctx": self.num_ctx, "num_predict": max_tokens}
        if seed is not None:
            opts["seed"] = seed
        if stop:
            opts["stop"] = stop
        payload = {"model": self.model, "messages": messages, "stream": False, "options": opts}
        if self.think is not None:
            payload["think"] = self.think
        for attempt in range(RETRIES + 1):
            try:
                r = requests.post(f"{self.base}/api/chat", timeout=self.timeout, json=payload)
                if r.status_code == 400 and "think" in payload and "think" in r.text.lower():
                    payload.pop("think")  # model has no thinking switch; use its default
                    self.think = None
                    continue
                if r.status_code < 500 or attempt == RETRIES:
                    r.raise_for_status()
                    break
            except (requests.ConnectionError, requests.Timeout):
                if attempt == RETRIES:
                    raise
            # 5xx / dropped connection: usually a full request queue or a model reload; back off
            time.sleep(BACKOFF[min(attempt, len(BACKOFF) - 1)])
        data = r.json()
        self.usage.add(data)
        return THINK_RE.sub("", data["message"].get("content", ""))

    def ask(self, prompt, system=None, **kw):
        msgs = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": prompt}]
        return self.chat(msgs, **kw)
