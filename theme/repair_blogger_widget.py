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

# Blogger serialises the CSS bullet glyph inconsistently. Remove the pseudo-
# element completely and use a plain border separator so there is no entity to
# leak into the visible ticker.
old_ticker_css = ".ticker-item{font-size:12px;color:#d5dce5}.ticker-item:before{content:'•';color:var(--green);margin-right:9px}"
new_ticker_css = ".ticker-item{font-size:12px;color:#d5dce5;padding-left:16px;border-left:1px solid #3a4657}.ticker-item:first-child{padding-left:0;border-left:0}"
if old_ticker_css in text:
    text = text.replace(old_ticker_css, new_ticker_css, 1)
elif new_ticker_css not in text:
    raise SystemExit("Ticker CSS block not found")

# Strip any already-mangled bullet/entity prefix that Blogger may expose in a
# headline string. This is defensive; visual separation is now CSS-only.
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

# The previous homepage preferred Blogger's media$thumbnail field, which was
# resolving to the generic EdgeAI fallback. Always inspect article HTML first
# and use the embedded article hero image. media$thumbnail is only a fallback.
old_thumb = "function thumb(e){if(e.media$thumbnail&&e.media$thumbnail.url)return e.media$thumbnail.url.replace(/\\/s72-c\\//,'/s1200/');var m=raw(e).match(/<img[^>]+src=[\"']([^\"']+)/i);return m?m[1]:fallback;}"
new_thumb = "function thumb(e){var h=raw(e),m=h.match(/<figure[^>]*class=[\"'][^\"']*edge-article-hero[^\"']*[\"'][\\s\\S]*?<img[^>]+src=[\"']([^\"']+)/i);if(!m)m=h.match(/<img[^>]+src=[\"']([^\"']+)/i);if(m&&m[1])return m[1];if(e.media$thumbnail&&e.media$thumbnail.url)return e.media$thumbnail.url.replace(/\\/s72-c\\//,'/s1200/');return fallback;}"
if old_thumb in text:
    text = text.replace(old_thumb, new_thumb, 1)
elif new_thumb not in text:
    raise SystemExit("Homepage thumbnail helper not found")

# Excerpts should contain the article copy, not image captions or the Evidence
# Trust card that sits above it in the article body.
old_plain = "function plain(e,n){var d=document.createElement('div');d.innerHTML=raw(e);var t=(d.textContent||'').replace(/Evidence Trust[^.]*\\./i,'').replace(/Image:[^\\n]*/i,'').replace(/\\s+/g,' ').trim();return t.slice(0,n||180)+(t.length>(n||180)?'…':'');}"
new_plain = "function plain(e,n){var d=document.createElement('div');d.innerHTML=raw(e);var kill=d.querySelectorAll('.edge-trust-card,.edge-article-hero');for(var i=0;i<kill.length;i++)kill[i].remove();var t=(d.textContent||'').replace(/\\s+/g,' ').trim();return t.slice(0,n||180)+(t.length>(n||180)?'…':'');}"
if old_plain in text:
    text = text.replace(old_plain, new_plain, 1)
elif new_plain not in text:
    raise SystemExit("Homepage excerpt helper not found")

# Blogger may strip data-* attributes from feed HTML. If that happens, recover
# the score/label from the visible Evidence Trust text so cards do not show
# 'Trust pending' when the article is already rated.
old_trust = "function trust(e){var s=raw(e),m=s.match(/data-trust-score=[\"'](\\d+)[\"']/i),l=s.match(/data-trust-label=[\"']([^\"']+)[\"']/i),n=m?parseInt(m[1],10):0;return{score:n,label:l?l[1]:'Unrated',color:n>=90?'#79d0ad':n>=75?'#8aa4ff':n>=60?'#d8b86d':'#dc7f8a'};}"
new_trust = "function trust(e){var s=raw(e),m=s.match(/data-trust-score=[\"'](\\d+)[\"']/i),l=s.match(/data-trust-label=[\"']([^\"']+)[\"']/i),txt=document.createElement('div');txt.innerHTML=s;var q=(txt.textContent||'').replace(/\\s+/g,' '),tm=q.match(/Evidence Trust[^0-9]{0,80}(\\d{1,3})/i),tl=q.match(/Evidence Trust[^A-Za-z]{0,20}[^ ]+\\s+(Verified|Strong|Reasonable|Caution|Low confidence)/i),n=m?parseInt(m[1],10):(tm?parseInt(tm[1],10):0),label=l?l[1]:(tl?tl[1]:'Unrated');return{score:n,label:label,color:n>=90?'#79d0ad':n>=75?'#8aa4ff':n>=60?'#d8b86d':'#dc7f8a'};}"
if old_trust in text:
    text = text.replace(old_trust, new_trust, 1)
elif new_trust not in text:
    raise SystemExit("Homepage trust helper not found")

path.write_text(text, encoding="utf-8")
print("Blogger theme repaired: widget-safe, entity-free ticker, article-first imagery, clean excerpts")
