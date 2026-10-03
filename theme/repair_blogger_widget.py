#!/usr/bin/env python3
from pathlib import Path

path = Path(__file__).with_name("EDGEAI_THEME.xml")
text = path.read_text(encoding="utf-8")
old = "<b:widget id='Blog1' locked='true' type='Blog'/>"
new = "<b:widget id='Blog1' locked='true' title='Blog Posts' type='Blog' version='2' visible='true'/>"
if old not in text and new not in text:
    raise SystemExit("Expected Blog1 declaration not found; refusing blind theme rewrite")
if old in text:
    text = text.replace(old, new, 1)
path.write_text(text, encoding="utf-8")
print("Blogger Blog1 declaration is now migration-safe")
