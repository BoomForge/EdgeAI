#!/usr/bin/env python3
from pathlib import Path

path = Path(__file__).resolve().parents[1] / "edgeai_editor.py"
text = path.read_text(encoding="utf-8")

old_bad = '    bad = ("favicon", "avatar", "logo-small", "icon-", "sprite", "emoji", "badge")\n    return not any(token in lower for token in bad)'
new_bad = '''    bad = (
        "favicon", "avatar", "logo-small", "icon-", "sprite", "emoji", "badge",
        "placeholder", "%3clink", "%3cimage", "<link", "<image", "opengraph,%20twitter-cards",
        "opengraph%2c%20twitter-cards", "path%20of%20image", "your-image", "example.com/image",
    )
    return not any(token in lower for token in bad)'''
if old_bad in text:
    text = text.replace(old_bad, new_bad, 1)
elif new_bad not in text:
    raise SystemExit("Image candidate validator block not found")

old_skip = '''        post = core.blogger("GET", f"blogs/{blog_id}/posts/{post_id}", access)
        content = str(post.get("content", ""))
        if "edge-article-hero" in content:
            skipped += 1
            continue

        item = find_queue_item(str(source_urls[-1]), str(story.get("trust", {}).get("source", "")))'''
new_skip = '''        post = core.blogger("GET", f"blogs/{blog_id}/posts/{post_id}", access)
        content = str(post.get("content", ""))
        # Visual mode is a repair pass: remove any previous hero block so a bad
        # placeholder/fallback can be replaced with newly discovered source art.
        content = re.sub(
            r'<figure class="edge-article-hero"[\\s\\S]*?</figure>\\s*',
            '',
            content,
            count=1,
            flags=re.IGNORECASE,
        )

        item = find_queue_item(str(source_urls[-1]), str(story.get("trust", {}).get("source", "")))'''
if old_skip in text:
    text = text.replace(old_skip, new_skip, 1)
elif new_skip not in text:
    raise SystemExit("Visual backfill skip block not found")

path.write_text(text, encoding="utf-8")
print("EdgeAI editor image validation and forced visual refresh patched")
