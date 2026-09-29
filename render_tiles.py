#!/usr/bin/env python3
"""Render a 5x3 'AI Ops Layer' tile set (72x72 PNG per key) from a state JSON.

Layout (Stream Deck MK.2):
  Row 0: [TITLE] [RUNNING n] [WAITING n] [FAILED n] [PAUSE/RESUME]
  Row 1: agent slots 1-5
  Row 2: agent slots 6-10
"""
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

TILE = 72
COLS, ROWS = 5, 3
OUT_DIR = Path(__file__).parent / "tiles"

STATUS_COLOR = {
    "running": (0, 180, 255),    # cyan
    "waiting": (255, 180, 0),    # amber
    "failed":  (255, 60, 60),    # red
    "done":    (60, 210, 120),   # green
    "idle":    (90, 90, 100),    # gray
}
STATUS_LABEL = {
    "running": "RUN",
    "waiting": "WAIT",
    "failed": "FAIL",
    "done": "DONE",
    "idle": "IDLE",
}
BG = (18, 18, 22)
FG = (235, 235, 240)
DIM = (140, 140, 150)


def font(size: int) -> ImageFont.FreeTypeFont:
    for p in (
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
    ):
        if Path(p).exists():
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                continue
    return ImageFont.load_default()


F_NAME = font(13)
F_SMALL = font(10)
F_BIG = font(24)


def fit(draw: ImageDraw.ImageDraw, text: str, fnt, width: int) -> str:
    """Truncate text with ellipsis so it fits `width` px."""
    if draw.textlength(text, font=fnt) <= width:
        return text
    while text and draw.textlength(text + "…", font=fnt) > width:
        text = text[:-1]
    return text + "…" if text else ""


def tile_bg() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", (TILE, TILE), BG)
    return img, ImageDraw.Draw(img)


def header_tile(label: str, value: str, color: tuple) -> Image.Image:
    img, d = tile_bg()
    d.rectangle([0, 0, TILE - 1, TILE - 1], outline=color, width=2)
    d.text((TILE / 2, 20), value, font=F_BIG, fill=color, anchor="mm")
    d.text((TILE / 2, 50), label, font=F_SMALL, fill=DIM, anchor="mm")
    return img


def title_tile(source: str, n: int) -> Image.Image:
    img, d = tile_bg()
    d.rectangle([0, 0, TILE - 1, TILE - 1], outline=(120, 90, 255), width=2)
    d.text((TILE / 2, 22), "AI OPS", font=F_NAME, fill=(160, 130, 255), anchor="mm")
    d.text((TILE / 2, 42), source.upper(), font=F_SMALL, fill=DIM, anchor="mm")
    d.text((TILE / 2, 58), f"{n} agents", font=F_SMALL, fill=DIM, anchor="mm")
    return img


def control_tile(paused: bool) -> Image.Image:
    img, d = tile_bg()
    color = (255, 180, 0) if not paused else (60, 210, 120)
    label = "PAUSE" if not paused else "RESUME"
    d.rectangle([0, 0, TILE - 1, TILE - 1], outline=color, width=2)
    d.ellipse([26, 14, 46, 34], fill=color)
    d.text((TILE / 2, 52), label, font=F_SMALL, fill=color, anchor="mm")
    return img


def agent_tile(agent: dict) -> Image.Image:
    img, d = tile_bg()
    color = STATUS_COLOR.get(agent.get("status", "idle"), (90, 90, 100))

    # status bar on top
    d.rectangle([0, 0, TILE, 6], fill=color)
    # agent name
    name = fit(d, agent.get("name", "?"), F_NAME, TILE - 8)
    d.text((TILE / 2, 18), name, font=F_NAME, fill=FG, anchor="mm")
    # task / note
    sub = agent.get("note") or agent.get("task") or STATUS_LABEL[agent.get("status", "idle")]
    sub = fit(d, sub, F_SMALL, TILE - 8)
    d.text((TILE / 2, 34), sub, font=F_SMALL, fill=DIM, anchor="mm")
    # status label + eta
    status = STATUS_LABEL.get(agent.get("status", "idle"), "?")
    eta = agent.get("eta", "")
    d.text((TILE / 2, 48), f"{status} {eta}".strip(), font=F_SMALL, fill=color, anchor="mm")
    # progress bar
    pct = max(0, min(100, int(agent.get("progress", 0))))
    d.rectangle([6, 62, TILE - 6, 68], outline=DIM, width=1)
    if pct > 0:
        w = int((TILE - 12) * pct / 100)
        d.rectangle([6, 62, 6 + w, 68], fill=color)
    return img


def render(state: dict, paused: bool = False) -> list[Image.Image]:
    agents = state.get("agents", [])[:10]
    counts = {s: sum(1 for a in agents if a.get("status") == s)
              for s in ("running", "waiting", "failed")}

    tiles = [
        title_tile(state.get("source", "herdr"), len(agents)),
        header_tile("RUNNING", str(counts["running"]), STATUS_COLOR["running"]),
        header_tile("WAITING", str(counts["waiting"]), STATUS_COLOR["waiting"]),
        header_tile("FAILED", str(counts["failed"]), STATUS_COLOR["failed"]),
        control_tile(paused),
    ]
    tiles += [agent_tile(a) for a in agents]
    tiles += [agent_tile({"name": "-", "status": "idle", "progress": 0})
              for _ in range(COLS * ROWS - len(tiles))]
    return tiles


def main() -> None:
    state_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent / "state.example.json"
    state = json.loads(state_path.read_text())
    if not OUT_DIR.exists():
        OUT_DIR.mkdir(exist_ok=True)
    tiles = render(state)
    for i, t in enumerate(tiles):
        t.save(OUT_DIR / f"key_{i:02d}.png")

    # composite preview of the whole deck
    pad = 8
    preview = Image.new("RGB", (COLS * TILE + (COLS + 1) * pad, ROWS * TILE + (ROWS + 1) * pad), (40, 40, 45))
    for i, t in enumerate(tiles):
        x = pad + (i % COLS) * (TILE + pad)
        y = pad + (i // COLS) * (TILE + pad)
        preview.paste(t, (x, y))
    preview.save(OUT_DIR / "preview.png", )
    print(f"rendered {len(tiles)} tiles -> {OUT_DIR}")


if __name__ == "__main__":
    main()
