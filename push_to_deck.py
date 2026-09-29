#!/usr/bin/env python3
"""Push the AI Ops Layer to a physical Stream Deck MK.2.

Usage:
  python push_to_deck.py [state.json]          # render once and exit
  python push_to_deck.py [state.json] --watch  # watch state file, live update
"""
import json
import os
import shutil
import sys
import time
from pathlib import Path

# --- portable hidapi: if a lib/ dir sits next to this package and DYLD_LIBRARY_PATH
# is not set, re-exec ourselves with it (dyld only reads the env at launch) ---
_HERE = Path(__file__).resolve().parent
_LIBDIR = _HERE / "lib"
if (_LIBDIR / "libhidapi.dylib").exists() and not os.environ.get("DYLD_LIBRARY_PATH"):
    os.environ["DYLD_LIBRARY_PATH"] = str(_LIBDIR)
    os.execv(sys.executable, getattr(sys, "orig_argv", [sys.executable] + sys.argv))

from StreamDeck.DeviceManager import DeviceManager
from StreamDeck.ImageHelpers import PILHelper

sys.path.insert(0, str(Path(__file__).parent))
from render_tiles import render  # noqa: E402

# herdr binary: env override -> ~/.local/bin/herdr -> PATH
HERDR = os.environ.get("HERDR_BIN") or str(Path.home() / ".local/bin/herdr")
if not Path(HERDR).exists():
    HERDR = shutil.which("herdr") or HERDR

STATE_PATH = Path(sys.argv[1]) if len(sys.argv) > 1 and not sys.argv[1].startswith("-") \
    else Path(__file__).parent / "state.example.json"
WATCH = "--watch" in sys.argv


def push(deck, state, paused):
    for i, tile in enumerate(render(state, paused)):
        deck.set_key_image(i, PILHelper.to_native_format(deck, tile))


def main():
    decks = DeviceManager().enumerate()
    if not decks:
        print("no stream deck found")
        sys.exit(1)
    deck = decks[0]
    deck.open()
    deck.reset()
    deck.set_brightness(80)

    paused = False

    def on_key(deck, key, pressed):
        nonlocal paused
        if not pressed:
            return
        print(f"key {key} pressed")
        if key == 4:  # PAUSE/RESUME toggle
            paused = not paused
            push(deck, json.loads(STATE_PATH.read_text()), paused)
            print("paused:", paused)
            return
        # keys 5-14 -> agent slots: focus that agent in herdr + jump iTerm to front
        if key >= 5:
            try:
                agents = json.loads(STATE_PATH.read_text()).get("agents", [])
                idx = key - 5
                if idx < len(agents) and agents[idx].get("id"):
                    import subprocess
                    subprocess.run([HERDR, "agent", "focus", agents[idx]["id"]],
                                   capture_output=True, timeout=5)
                    subprocess.run(["osascript", "-e",
                                    'tell application "iTerm2" to activate'],
                                   capture_output=True, timeout=5)
                    print(f"jump to agent: {agents[idx]['name']} ({agents[idx]['id']})", flush=True)
            except Exception as e:
                print("focus failed:", e, flush=True)

    deck.set_key_callback(on_key)

    state = json.loads(STATE_PATH.read_text())
    push(deck, state, paused)
    print(f"pushed AI Ops Layer from {STATE_PATH.name} "
          f"({len(state.get('agents', []))} agents), brightness 80%")

    if not WATCH:
        deck.close()
        return

    print("watching state file for changes... (Ctrl-C to stop)")
    last_mtime = STATE_PATH.stat().st_mtime
    try:
        while True:
            time.sleep(1)
            mtime = STATE_PATH.stat().st_mtime
            if mtime != last_mtime:
                last_mtime = mtime
                try:
                    state = json.loads(STATE_PATH.read_text())
                    push(deck, state, paused)
                    print(f"[{time.strftime('%H:%M:%S')}] updated")
                except json.JSONDecodeError:
                    pass  # partial write, retry next tick
    except KeyboardInterrupt:
        pass
    finally:
        deck.reset()
        deck.close()


if __name__ == "__main__":
    main()
