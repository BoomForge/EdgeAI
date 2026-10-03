from __future__ import annotations

import hashlib
import re
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
ART_DIR = ROOT / "assets" / "story-art"
CDN_BASE = "https://cdn.jsdelivr.net/gh/BoomForge/EdgeAI@main/assets/story-art"

PALETTES = {
    "Models": ("#7e93ff", "#9a7cff"),
    "Tools": ("#5ec5b1", "#6f9cff"),
    "Agents": ("#58c8a5", "#b0d36f"),
    "Research": ("#d0a65d", "#8d79c9"),
    "Open Source": ("#67c08d", "#6b8ee8"),
    "Creative AI": ("#cc78a8", "#8176e7"),
    "Infrastructure": ("#72a2bd", "#7687a4"),
    "Breaking": ("#df826f", "#d8ae61"),
}


def _safe_key(value: str) -> str:
    value = re.sub(r"[^a-z0-9-]+", "-", value.lower()).strip("-")
    return value[:100] or "story"


def _category(labels: list[str] | None) -> str:
    labels = labels or []
    for name in PALETTES:
        if name in labels:
            return name
    return "Models"


def _lines(title: str) -> list[str]:
    title = re.sub(r"\s+", " ", title).strip()
    lines = textwrap.wrap(title, width=31, break_long_words=False, break_on_hyphens=False)
    if len(lines) > 3:
        lines = lines[:3]
        lines[-1] = lines[-1][:27].rstrip() + "…"
    return lines or ["EdgeAI Report"]


def _font(size: int, bold: bool = False):
    names = [
        "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default()


def _rgb(hex_color: str) -> tuple[int, int, int]:
    value = hex_color.lstrip("#")
    return tuple(int(value[i:i+2], 16) for i in (0, 2, 4))


def ensure_story_art(story_key: str, title: str, source: str, labels: list[str] | None = None) -> str:
    """Generate a Blogger-safe PNG cover and return its public CDN URL."""
    ART_DIR.mkdir(parents=True, exist_ok=True)
    key = _safe_key(story_key)
    path = ART_DIR / f"{key}.png"

    width, height = 1200, 675
    category = _category(labels)
    c1, c2 = PALETTES[category]
    c1_rgb, c2_rgb = _rgb(c1), _rgb(c2)

    img = Image.new("RGB", (width, height), (10, 14, 20))
    draw = ImageDraw.Draw(img, "RGBA")

    for y in range(height):
        p = y / max(1, height - 1)
        base = (int(11 + 10 * p), int(15 + 10 * p), int(22 + 12 * p))
        draw.line((0, y, width, y), fill=(*base, 255))

    for x in range(0, width, 44):
        draw.line((x, 0, x, height), fill=(255, 255, 255, 8), width=1)
    for y in range(0, height, 44):
        draw.line((0, y, width, y), fill=(255, 255, 255, 8), width=1)

    digest = hashlib.sha256((story_key + title).encode("utf-8")).hexdigest()
    nums = [int(digest[i:i+8], 16) for i in (0, 8, 16)]
    for i, n in enumerate(nums):
        cx = 760 + (n % 330)
        cy = 100 + ((n // 13) % 470)
        r = 90 + ((n // 101) % 150)
        col = c1_rgb if i % 2 == 0 else c2_rgb
        draw.ellipse((cx-r, cy-r, cx+r, cy+r), outline=(*col, 70 + i * 18), width=2)

    draw.line([(690, 555), (805, 455), (918, 488), (1132, 344)], fill=(*c1_rgb, 150), width=3, joint="curve")
    draw.line([(715, 590), (845, 495), (958, 522), (1168, 406)], fill=(223, 231, 242, 45), width=2, joint="curve")

    draw.rounded_rectangle((72, 64, 198, 100), radius=7, fill=(*c1_rgb, 255))
    draw.text((87, 72), "EDGEAI", font=_font(17, True), fill=(12, 17, 24, 255))
    draw.text((72, 132), category.upper(), font=_font(16, True), fill=(*c1_rgb, 255))

    title_font = _font(48, True)
    lines = _lines(title)
    y = 255 - (len(lines) - 1) * 35
    for line in lines:
        draw.text((72, y), line, font=title_font, fill=(244, 247, 251, 255))
        y += 62

    draw.line((72, 540, 558, 540), fill=(255, 255, 255, 38), width=1)
    source_text = re.sub(r"\s+", " ", source or "EdgeAI").strip()[:60].upper()
    draw.text((72, 566), f"SOURCE / {source_text}", font=_font(17), fill=(170, 181, 195, 255))
    draw.text((72, 608), "BLEEDING-EDGE AI WITHOUT THE NOISE", font=_font(14), fill=(125, 137, 152, 255))
    draw.text((930, 608), "SIGNAL / VERIFY / REPORT", font=_font(14), fill=(116, 128, 145, 255))

    img.save(path, format="PNG", optimize=True)
    return f"{CDN_BASE}/{path.name}"
