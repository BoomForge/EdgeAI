#!/usr/bin/env python3
from pathlib import Path

path = Path(__file__).with_name("EDGEAI_THEME.xml")
text = path.read_text(encoding="utf-8")

# Keep Blogger's native Blog1 declaration explicit so Edit HTML does not try to
# migrate the widget while saving the surrounding custom newsroom markup.
old_widget = "<b:widget id='Blog1' locked='true' type='Blog'/>"
new_widget = "<b:widget id='Blog1' locked='true' title='Blog Posts' type='Blog' version='2' visible='true'/>"
if old_widget in text:
    text = text.replace(old_widget, new_widget, 1)
elif new_widget not in text:
    raise SystemExit("Expected Blog1 declaration not found; refusing blind theme rewrite")

# Blogger can occasionally expose the HTML bullet entity as literal '#8226;'
# inside JSONP-rendered ticker headlines. Strip any such prefix in JavaScript
# and let CSS draw the visual separator instead.
esc_fn = "function esc(v){var d=document.createElement('div');d.textContent=v||'';return d.innerHTML;}"
clean_fn = "function cleanTickerTitle(v){return String(v||'').replace(/^(?:&?#?8226;|&#x2022;|•)\\s*/i,'').trim();}"
if clean_fn not in text:
    if esc_fn not in text:
        raise SystemExit("Ticker helper insertion point not found")
    text = text.replace(esc_fn, esc_fn + "\n" + clean_fn, 1)

old_ticker = "esc(es[i].title.$t)+'</a>'"
new_ticker = "esc(cleanTickerTitle(es[i].title.$t))+'</a>'"
if old_ticker in text:
    text = text.replace(old_ticker, new_ticker, 1)
elif new_ticker not in text:
    raise SystemExit("Ticker title render expression not found")

path.write_text(text, encoding="utf-8")
print("Blogger Blog1 declaration and ticker rendering are migration-safe")
