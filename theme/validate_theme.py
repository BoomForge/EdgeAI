#!/usr/bin/env python3
from pathlib import Path
import re
import xml.etree.ElementTree as ET

path = Path(__file__).with_name("EDGEAI_THEME.xml")
text = path.read_text(encoding="utf-8")
ET.fromstring(text)

required = [
    "<b:skin>",
    "edgeai-ticker",
    "edgeai-hero",
    "edgeai-trending",
    "<b:widget id='Blog1'",
    "/search/label/Models",
    "/search/label/Research",
    "/search/label/Agents",
    "CONFIRMED",
    "DEVELOPING",
    "EARLY%20SIGNAL",
    "RUMOUR",
]
missing = [item for item in required if item not in text]
if missing:
    raise SystemExit(f"Theme missing required newsroom elements: {missing}")

if text.count("<b:skin>") != 1 or text.count("</b:skin>") != 1:
    raise SystemExit("Blogger theme must contain exactly one b:skin block")
if text.count("<b:section") != 1:
    raise SystemExit("Safe theme must contain exactly one native Blogger section")
if text.count("<b:widget") != 1:
    raise SystemExit("Safe theme must contain exactly one native Blogger widget")
if "PopularPosts1" in text or "Label1" in text:
    raise SystemExit("Import-fragile sidebar widgets must not be embedded in safe theme")
if not re.search(r"feeds/posts/default.*callback=edgeAITicker", text):
    raise SystemExit("Ticker feed loader missing")
if not re.search(r"feeds/posts/default/-/Featured.*callback=edgeAIHero", text):
    raise SystemExit("Featured hero feed loader missing")
if not re.search(r"feeds/posts/default.*callback=edgeAITrending", text):
    raise SystemExit("Trending feed loader missing")

print("EDGEAI BLOGGER THEME: minimal Blogger-safe XML and newsroom contract OK")
