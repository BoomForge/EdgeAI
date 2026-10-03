#!/usr/bin/env python3
from pathlib import Path

path = Path(__file__).resolve().parents[1] / "edgeai_editor.py"
text = path.read_text(encoding="utf-8")

imp = "import edgeai as core\n"
new_imp = "import edgeai as core\nfrom story_art import ensure_story_art\n"
if new_imp not in text:
    if imp not in text:
        raise SystemExit("edgeai import anchor missing")
    text = text.replace(imp, new_imp, 1)

old_publish = '''    image_url, image_source = extract_source_image(item)\n    body = (\n        hero_media(image_url, image_source, title)\n        + trust_card(trust_score, trust_name, trust_reason, str(item.get("source_name", "Source")))\n        + body\n    )\n\n    labels = add_featured(core.safe_labels(decision.get("labels"), status), score)\n'''
new_publish = '''    labels = add_featured(core.safe_labels(decision.get("labels"), status), score)\n    source_image_url, source_image_source = extract_source_image(item)\n    image_url = ensure_story_art(\n        skey, title, str(item.get("source_name", "Source")), labels\n    )\n    image_source = "EdgeAI editorial artwork"\n    body = (\n        hero_media(image_url, image_source, title)\n        + trust_card(trust_score, trust_name, trust_reason, str(item.get("source_name", "Source")))\n        + body\n    )\n'''
if old_publish in text:
    text = text.replace(old_publish, new_publish, 1)
elif "ensure_story_art(\n        skey, title" not in text:
    raise SystemExit("publish image block anchor missing")

old_story = '''        "image_url": image_url,\n        "image_source": image_source,\n        "source_urls": source_urls,\n'''
new_story = '''        "image_url": image_url,\n        "image_source": image_source,\n        "source_image_url": source_image_url,\n        "source_image_source": source_image_source,\n        "source_urls": source_urls,\n'''
if old_story in text:
    text = text.replace(old_story, new_story, 1)

old_visual = '''        item = find_queue_item(str(source_urls[-1]), str(story.get("trust", {}).get("source", "")))\n        item["title"] = story.get("title", item.get("title", ""))\n        image_url, image_source = extract_source_image(item)\n        title = str(post.get("title") or story.get("title") or "EdgeAI report")\n        payload = {\n            "kind": "blogger#post",\n            "title": title,\n            "content": hero_media(image_url, image_source, title) + content,\n            "labels": post.get("labels", []),\n        }\n'''
new_visual = '''        item = find_queue_item(str(source_urls[-1]), str(story.get("trust", {}).get("source", "")))\n        item["title"] = story.get("title", item.get("title", ""))\n        title = str(post.get("title") or story.get("title") or "EdgeAI report")\n        labels = post.get("labels", [])\n        source_image_url, source_image_source = extract_source_image(item)\n        image_url = ensure_story_art(\n            skey, title, str(story.get("trust", {}).get("source", item.get("source_name", "Source"))), labels\n        )\n        image_source = "EdgeAI editorial artwork"\n        payload = {\n            "kind": "blogger#post",\n            "title": title,\n            "content": hero_media(image_url, image_source, title) + content,\n            "labels": labels,\n        }\n'''
if old_visual in text:
    text = text.replace(old_visual, new_visual, 1)
elif "image_url = ensure_story_art(\n            skey, title" not in text:
    raise SystemExit("visual image block anchor missing")

old_visual_story = '''        story["image_url"] = image_url\n        story["image_source"] = image_source\n        story["post_url"] = result.get("url", story.get("post_url", ""))\n'''
new_visual_story = '''        story["image_url"] = image_url\n        story["image_source"] = image_source\n        story["source_image_url"] = source_image_url\n        story["source_image_source"] = source_image_source\n        story["post_url"] = result.get("url", story.get("post_url", ""))\n'''
if old_visual_story in text:
    text = text.replace(old_visual_story, new_visual_story, 1)

path.write_text(text, encoding="utf-8")
print("EdgeAI story artwork integration installed")
