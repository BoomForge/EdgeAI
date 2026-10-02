#!/usr/bin/env python3
from pathlib import Path
import re
import xml.etree.ElementTree as ET

path = Path(__file__).with_name("EDGEAI_THEME.xml")
text = path.read_text(encoding="utf-8")
ET.fromstring(text)

required = [
    "edgeai-ticker",
    "edgeai-hero",
    "PopularPosts1",
    "Label1",
    "/search/label/Models",
    "/search/label/Research",
    "/search/label/Agents",
    "CONFIRMED",
    "DEVELOPING",
    "EARLY SIGNAL",
    "RUMOUR",
]
missing = [item for item in required if item not in text]
if missing:
    raise SystemExit(f"Theme missing required newsroom elements: {missing}")

if text.count("<b:section") < 2:
    raise SystemExit("Theme requires main and sidebar Blogger sections")
if not re.search(r"feeds/posts/default.*callback=edgeAITicker", text):
    raise SystemExit("Ticker feed loader missing")
if not re.search(r"feeds/posts/default/-/Featured.*callback=edgeAIHero", text):
    raise SystemExit("Featured hero feed loader missing")

print("EDGEAI BLOGGER THEME: XML and newsroom contract OK")
