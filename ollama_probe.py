"""Standalone, side-effect-free connectivity probe for a local Ollama
server -- confirms the exact request shape WAPLA_AIG_Engine.py's local-model
path (_ollama_direct_chat()) uses actually reaches the server, before the
full pipeline run commits any real work to it. Does not touch any
WAPLA_AIG_Engine.py output file (no audit trail, no token-usage log, no
deliverable CSV).

Run on the SAME node as `ollama serve` (or with OLLAMA_HOST pointed at it):

    python ollama_probe.py qwen2.5:7b
    python ollama_probe.py qwen2.5:7b llama3.1:8b   # probes both models

Reports, per model: whether the call succeeded, the response content, and
wall-clock latency (first call for a not-yet-loaded model will include
Ollama's model-load time -- run it once per model before timing the real
pipeline run so that load cost isn't misattributed to per-item generation
latency).

DELIBERATELY BYPASSES litellm, calling Ollama's /api/chat directly via
aiohttp -- matching WAPLA_AIG_Engine.py's own local-model path. History:
an earlier version of this probe (and the engine) went through
litellm.acompletion(model="ollama_chat/...", ...), which mysteriously
aborted a slow first load around ~300-400s even after setting litellm's
GLOBAL request_timeout to 600s (litellm 1.55.0's ollama_chat handler
reads ONLY that global for its total timeout -- confirmed by reading
litellm/main.py and llms/ollama_chat.py's source directly -- and does not
honor a per-call `timeout=` kwarg at all). Tracing aiohttp.ClientTimeout's
sub-fields (sock_read/sock_connect) showed litellm passes only `total=`,
leaving those at their default of None (no separate sub-timeout) --
so the ~300-400s cutoff's exact origin inside litellm was never fully
pinned down. A direct `curl` against the same endpoint succeeded
end-to-end (~172s for a 13GB model on NFS-backed storage), proving Ollama
and the network are fine -- so this probe (and the engine) now issue the
same direct HTTP request `curl` used, under our own full control.
"""
import asyncio
import json
import os
import sys
import time

import aiohttp
from dotenv import load_dotenv

load_dotenv()

LOAD_TIMEOUT = 600  # seconds; keep in sync with WAPLA_AIG_Engine.py's --ollama-load-timeout
NUM_CTX = 8192  # keep in sync with WAPLA_AIG_Engine.py's --ollama-num-ctx
KEEP_ALIVE = "30m"  # keep in sync with WAPLA_AIG_Engine.py's --ollama-keep-alive


def _api_base() -> str:
    base = (os.environ.get("OLLAMA_HOST") or os.environ.get("OLLAMA_API_BASE")
            or "http://localhost:11434").rstrip("/")
    return base if base.endswith("/api/chat") else f"{base}/api/chat"


async def probe(model: str) -> None:
    url = _api_base()
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "Reply with exactly: OK"}],
        "stream": False,
        "keep_alive": KEEP_ALIVE,
        "options": {"num_ctx": NUM_CTX, "temperature": 0.0},
    }
    t0 = time.monotonic()
    try:
        timeout = aiohttp.ClientTimeout(total=LOAD_TIMEOUT)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, json=payload) as resp:
                body_text = await resp.text()
                elapsed = time.monotonic() - t0
                if resp.status != 200:
                    print(f"[{model}] FAILED after {elapsed:.1f}s -- HTTP {resp.status}: "
                          f"{body_text[:500]}")
                    return
                data = json.loads(body_text)
        content = data.get("message", {}).get("content")
        load_duration_s = data.get("load_duration", 0) / 1e9
        eval_duration_s = data.get("eval_duration", 0) / 1e9
        print(f"[{model}] SUCCESS in {elapsed:.1f}s (Ollama-reported load={load_duration_s:.1f}s, "
              f"eval={eval_duration_s:.1f}s) -- content={content!r}")
    except asyncio.TimeoutError:
        elapsed = time.monotonic() - t0
        print(f"[{model}] TIMED OUT after {elapsed:.1f}s (LOAD_TIMEOUT={LOAD_TIMEOUT}s)")
    except Exception as exc:  # noqa: BLE001
        elapsed = time.monotonic() - t0
        print(f"[{model}] FAILED after {elapsed:.1f}s -- {exc}")
        print(
            "  Checklist: is `ollama serve` running and reachable "
            f"({url})? Has `ollama pull {model}` completed? Does "
            "`ollama list` show it?"
        )


async def main() -> None:
    models = sys.argv[1:] or ["qwen2.5:7b"]
    for i, m in enumerate(models):
        if i > 0:
            await asyncio.sleep(1)
        await probe(m)


if __name__ == "__main__":
    asyncio.run(main())
