from __future__ import annotations

import hashlib
import html
import re
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ART_DIR = ROOT / "assets" / "story-art"
RAW_BASE = "https://raw.githubusercontent.com/BoomForge/EdgeAI/main/assets/story-art"

# EdgeAI-owned artwork is the guaranteed hero/thumbnail path. Source imagery is
# retained separately as evidence/supporting media, never as the availability dependency.
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
        if len(lines[-1]) > 27:
            lines[-1] = lines[-1][:27].rstrip()
        lines[-1] += "…"
    return lines or ["EdgeAI Report"]


def ensure_story_art(story_key: str, title: str, source: str, labels: list[str] | None = None) -> str:
    ART_DIR.mkdir(parents=True, exist_ok=True)
    key = _safe_key(story_key)
    path = ART_DIR / f"{key}.svg"

    category = _category(labels)
    c1, c2 = PALETTES[category]
    digest = hashlib.sha256((story_key + title).encode("utf-8")).hexdigest()
    n1 = int(digest[:8], 16)
    n2 = int(digest[8:16], 16)
    n3 = int(digest[16:24], 16)
    circles = []
    for i, n in enumerate((n1, n2, n3)):
        x = 720 + (n % 390)
        y = 100 + ((n // 11) % 470)
        r = 85 + ((n // 101) % 150)
        circles.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill="none" stroke="url(#g)" stroke-width="1.4" opacity="{0.16 + i*0.05:.2f}"/>')

    title_lines = _lines(title)
    text_nodes = []
    y = 300 - (len(title_lines) - 1) * 39
    for line in title_lines:
        text_nodes.append(f'<text x="72" y="{y}" fill="#f4f7fb" font-size="48" font-weight="800" font-family="Arial,Helvetica,sans-serif">{html.escape(line)}</text>')
        y += 58

    source = re.sub(r"\s+", " ", source or "EdgeAI").strip()[:60]
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="675" viewBox="0 0 1200 675">
<defs>
  <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#0b1018"/><stop offset="1" stop-color="#161b25"/></linearGradient>
  <linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop stop-color="{c1}"/><stop offset="1" stop-color="{c2}"/></linearGradient>
  <filter id="blur"><feGaussianBlur stdDeviation="38"/></filter>
  <pattern id="grid" width="44" height="44" patternUnits="userSpaceOnUse"><path d="M44 0H0V44" fill="none" stroke="#ffffff" stroke-opacity=".035" stroke-width="1"/></pattern>
</defs>
<rect width="1200" height="675" fill="url(#bg)"/>
<rect width="1200" height="675" fill="url(#grid)"/>
<circle cx="1010" cy="108" r="245" fill="{c1}" opacity=".12" filter="url(#blur)"/>
<circle cx="900" cy="585" r="220" fill="{c2}" opacity=".10" filter="url(#blur)"/>
{''.join(circles)}
<path d="M690 555 C805 455 918 488 1132 344" fill="none" stroke="url(#g)" stroke-width="2" opacity=".48"/>
<path d="M715 590 C845 495 958 522 1168 406" fill="none" stroke="#dfe7f2" stroke-width="1" opacity=".14"/>
<rect x="72" y="64" width="126" height="34" rx="6" fill="url(#g)"/>
<text x="135" y="87" text-anchor="middle" fill="#0c1118" font-size="16" font-weight="900" font-family="Arial,Helvetica,sans-serif">EDGEAI</text>
<text x="72" y="137" fill="{c1}" font-size="15" font-weight="800" letter-spacing="2.5" font-family="Arial,Helvetica,sans-serif">{html.escape(category.upper())}</text>
{''.join(text_nodes)}
<line x1="72" y1="540" x2="558" y2="540" stroke="#ffffff" stroke-opacity=".14"/>
<text x="72" y="579" fill="#aab5c3" font-size="17" font-family="Arial,Helvetica,sans-serif">SOURCE / {html.escape(source.upper())}</text>
<text x="72" y="616" fill="#7d8998" font-size="14" letter-spacing="1.5" font-family="Arial,Helvetica,sans-serif">BLEEDING-EDGE AI WITHOUT THE NOISE</text>
<text x="1112" y="622" text-anchor="end" fill="#748091" font-size="12" letter-spacing="1.3" font-family="Arial,Helvetica,sans-serif">SIGNAL / VERIFY / REPORT</text>
</svg>'''
    path.write_text(svg, encoding="utf-8")
    return f"{RAW_BASE}/{path.name}"
