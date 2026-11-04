"""Run model-written Python in a throwaway directory with a timeout.

This is process isolation only (temp cwd, isolated interpreter, scrubbed environment), not a
security boundary. Set TVASHTR_SANDBOX=docker to run inside a disposable container instead.
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass

CODE_BLOCK = re.compile(r"```(?:python|py|python3)?[ \t]*\r?\n(.*?)```", re.S | re.I)
OPEN_FENCE = re.compile(r"^\s*```[\w+-]*[ \t]*$", re.M)


def extract_code(text):
    """Largest fenced code block, or the raw text if the model skipped fences.

    Line endings are normalised first: some models emit CRLF, which would otherwise defeat the
    fence regex. An unterminated block (output cut off before the closing fence) is also handled.
    """
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    blocks = CODE_BLOCK.findall(text)
    if blocks:
        return max(blocks, key=len).strip("\n") + "\n"
    m = OPEN_FENCE.search(text)
    if m:  # opening fence without a closing one
        text = text[m.end():]
    return text.strip("\n") + "\n"


@dataclass
class Result:
    ok: bool
    stdout: str
    stderr: str
    timeout: bool = False


def _env():
    keep = {k: os.environ[k] for k in ("SYSTEMROOT", "SystemRoot", "TEMP", "TMP", "PATH") if k in os.environ}
    keep["PYTHONIOENCODING"] = "utf-8"
    keep["PYTHONHASHSEED"] = "0"
    return keep


def run(code, timeout=10.0):
    d = tempfile.mkdtemp(prefix="tvashtr-")
    try:
        path = os.path.join(d, "prog.py")
        with open(path, "w", encoding="utf-8") as f:
            f.write(code)
        if os.environ.get("TVASHTR_SANDBOX") == "docker":
            cmd = ["docker", "run", "--rm", "--network=none", "--memory=512m", "--cpus=1",
                   "-v", f"{d}:/w:ro", "-w", "/w", "python:3.12-slim", "python", "-I", "prog.py"]
            timeout += 5
        else:
            cmd = [sys.executable, "-I", path]
        p = subprocess.run(cmd, cwd=d, env=_env(), capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout,
                           stdin=subprocess.DEVNULL)
        return Result(p.returncode == 0, p.stdout[-4000:], p.stderr[-4000:])
    except subprocess.TimeoutExpired as e:
        return Result(False, (e.stdout or "")[-2000:] if isinstance(e.stdout, str) else "",
                      f"Timed out after {timeout}s", timeout=True)
    finally:
        shutil.rmtree(d, ignore_errors=True)


def run_tests(code, tests, timeout=10.0):
    """Run each assert separately; returns (passed, total, first_failure_message)."""
    if not tests:
        return 0, 0, None
    harness = [code, "\nimport traceback as __tb\n__r = []"]
    for t in tests:
        harness.append(f"try:\n    exec({t!r}, globals())\n    __r.append('P')\n"
                       f"except BaseException as __e:\n    __r.append('F' + repr({t!r}) + ' -> ' + "
                       f"(type(__e).__name__ + ': ' + str(__e))[:300])")
    harness.append("print('@@' + '\\x1f'.join(__r))")
    res = run("\n".join(harness), timeout)
    line = next((l for l in reversed(res.stdout.splitlines()) if l.startswith("@@")), None)
    if line is None:
        msg = "Timed out" if res.timeout else (res.stderr.strip().splitlines() or ["crashed"])[-1]
        return 0, len(tests), f"Program failed before tests ran: {msg}\n{res.stderr[-1500:]}"
    marks = line[2:].split("\x1f")
    passed = sum(m == "P" for m in marks)
    fail = next((m[1:] for m in marks if m != "P"), None)
    return passed, len(tests), fail


def outputs_on(code, inputs, timeout=10.0):
    """Execution signature of `code` on call expressions, used to cluster candidates (S*)."""
    if not inputs:
        return ()
    harness = [code, "\n__o = []"]
    for e in inputs:
        harness.append(f"try:\n    __o.append(repr(eval({e!r})))\nexcept BaseException as __x:\n"
                       f"    __o.append('EXC:' + type(__x).__name__)")
    harness.append("print('@@' + '\\x1f'.join(__o))")
    res = run("\n".join(harness), timeout)
    line = next((l for l in reversed(res.stdout.splitlines()) if l.startswith("@@")), None)
    return tuple(line[2:].split("\x1f")) if line else ("CRASH",) * len(inputs)
