# Copyright (c) 2026 Wneil2020 and the holon skill contributors. Released under the MIT License.
"""One chat call to an OpenAI-compatible endpoint.
LLM_BASE_URL (required), LLM_MODEL (default deepseek-v4.1-flash), LLM_API_KEY (optional; omit when a proxy adds it)."""
import json, os, subprocess, time
BASE = os.environ.get("LLM_BASE_URL", "").rstrip("/")
MODEL = os.environ.get("LLM_MODEL", "deepseek-v4.1-flash")
def chat(msgs, model=None, temperature=0, retries=8, timeout=90):
    if not BASE:
        raise SystemExit("set LLM_BASE_URL, e.g. https://api.example.com/v1")
    body = json.dumps({"model": model or MODEL, "messages": msgs, "temperature": temperature})
    cmd = ["curl", "-s", "--max-time", str(timeout), BASE + "/chat/completions", "-H", "Content-Type: application/json", "-d", "@-"]
    if os.environ.get("LLM_API_KEY"):
        cmd[5:5] = ["-H", "Authorization: Bearer " + os.environ["LLM_API_KEY"]]
    r = None
    for i in range(retries):
        r = subprocess.run(cmd, input=body, capture_output=True, text=True)
        try:
            return json.loads(r.stdout)["choices"][0]["message"]["content"]
        except Exception:
            time.sleep(4 * (i + 1))
    raise RuntimeError((r.stdout if r else "")[:300])
