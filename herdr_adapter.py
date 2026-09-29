#!/usr/bin/env python3
"""Bridge: herdr (herdr.dev) live agent state -> state.json for the Stream Deck AI Ops Layer.

Usage:
  python herdr_adapter.py                 # poll `herdr api snapshot` every 2s, write state.json
  python herdr_adapter.py --interval 5
  python herdr_adapter.py --from-file snapshot.json   # one-shot convert (testing)
  python herdr_adapter.py --once          # one-shot poll

Status mapping (herdr AgentStatus -> panel):
  working -> running | blocked -> waiting | done -> done | idle/unknown -> idle
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).parent
STATE_OUT = HERE / "state.json"

# herdr binary: env override -> ~/.local/bin/herdr -> PATH
HERDR = os.environ.get("HERDR_BIN") or str(Path.home() / ".local/bin/herdr")
if not Path(HERDR).exists():
    HERDR = shutil.which("herdr") or HERDR

STATUS_MAP = {
    "working": "running",
    "blocked": "waiting",
    "done": "done",
    "idle": "idle",
    "unknown": "idle",
}


def convert(snapshot: dict) -> dict:
    """Convert a herdr SessionSnapshot into the panel state contract."""
    agents = []
    for a in snapshot.get("agents", []):
        tokens = a.get("tokens") or {}
        note = None
        if tokens:
            # show first token metric, e.g. total/context
            key = "total" if "total" in tokens else next(iter(tokens))
            note = f"tok {tokens[key]}"
        title = a.get("name") or a.get("display_agent") or a.get("agent") or "agent"
        task = a.get("title") or a.get("terminal_title_stripped") or a.get("terminal_title") or ""
        cwd = a.get("foreground_cwd") or a.get("cwd") or ""
        agents.append({
            "id": a.get("pane_id"),
            "name": title,
            "task": task[:40],
            "status": STATUS_MAP.get(a.get("agent_status", "unknown"), "idle"),
            "progress": 100 if a.get("agent_status") == "done" else 0,
            "note": note,
            "cwd": Path(cwd).name if cwd else "",
            "focused": a.get("focused", False),
        })
    # blocked (waiting) agents float to the top, then working, then rest
    rank = {"waiting": 0, "running": 1, "failed": 2, "done": 3, "idle": 4}
    agents.sort(key=lambda x: rank.get(x["status"], 9))
    return {
        "source": "herdr",
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "agents": agents[:10],
    }


def unwrap(resp: dict) -> dict | None:
    """Extract SessionSnapshot from a CLI/API response.

    `herdr api snapshot` returns {"id": ..., "result": {"snapshot": {...}, "type": ...}}
    so the snapshot is one level deeper than `result`.
    """
    result = resp.get("result") or {}
    if "snapshot" in result:
        return result["snapshot"]
    return result if "agents" in result else None


def poll_snapshot() -> dict | None:
    """Run `herdr api snapshot`; return SessionSnapshot or None on error."""
    try:
        out = subprocess.run([HERDR, "api", "snapshot"], capture_output=True,
                             text=True, timeout=10)
        resp = json.loads(out.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError):
        return None
    if "error" in resp:
        return None
    return unwrap(resp)


def write_state(state: dict) -> None:
    """Atomic write so the renderer never reads a partial file."""
    with tempfile.NamedTemporaryFile("w", dir=HERE, suffix=".tmp", delete=False) as f:
        json.dump(state, f, ensure_ascii=False)
        tmp = f.name
    Path(tmp).replace(STATE_OUT)


def offline_state() -> dict:
    return {"source": "herdr", "updated_at": datetime.now(timezone.utc).isoformat(),
            "agents": [], "note": "herdr offline"}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--interval", type=float, default=2.0)
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--from-file", type=Path)
    args = ap.parse_args()

    if args.from_file:
        snap = json.loads(args.from_file.read_text())
        snap = unwrap(snap) or snap.get("result", snap)
        state = convert(snap)
        write_state(state)
        print(f"converted {len(state['agents'])} agents -> {STATE_OUT}")
        return

    while True:
        snap = poll_snapshot()
        state = convert(snap) if snap else offline_state()
        write_state(state)
        tag = time.strftime("%H:%M:%S")
        print(f"[{tag}] agents={len(state['agents'])}"
              + ("" if snap else " (herdr offline)"), flush=True)
        if args.once:
            return
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
