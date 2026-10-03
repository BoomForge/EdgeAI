#!/usr/bin/env python3
from __future__ import annotations

import html
import json
import re
from pathlib import Path

import requests

import edgeai as core
from story_art import ensure_story_art

ROOT = Path(__file__).resolve().parent
STATE_PATH = ROOT / "editor_state.json"
REPORT_PATH = ROOT / "image_repair_report.json"


def load_state() -> dict:
    return json.loads(STATE_PATH.read_text(encoding="utf-8"))


def save_state(state: dict) -> None:
    STATE_PATH.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def clean_old_hero(content: str) -> str:
    content = re.sub(
        r'<figure[^>]*class=["\'][^"\']*edge-article-hero[^"\']*["\'][^>]*>[\s\S]*?</figure>\s*',
        '', content, count=1, flags=re.IGNORECASE,
    )
    content = re.sub(
        r'^\s*<img[^>]+(?:raw\.githubusercontent\.com|cdn\.jsdelivr\.net)[^>]+>\s*',
        '', content, count=1, flags=re.IGNORECASE,
    )
    return content.lstrip()


def hero_html(url: str, title: str) -> str:
    return (
        '<figure class="edge-article-hero" style="margin:0 0 22px 0;">'
        f'<img src="{html.escape(url, quote=True)}" alt="{html.escape(title, quote=True)}" '
        'style="display:block;width:100%;height:auto;max-height:560px;object-fit:cover;'
        'border-radius:14px;border:1px solid #303846;background:#11161e;" />'
        '<figcaption style="margin-top:7px;font:11px/1.4 Arial,sans-serif;color:#8792a0;">'
        'Image: EdgeAI editorial artwork</figcaption></figure>'
    )


def verify_cdn(url: str) -> tuple[bool, str]:
    try:
        r = requests.get(url, timeout=20, headers={"User-Agent": core.USER_AGENT})
        ctype = r.headers.get("content-type", "").lower()
        ok = r.status_code == 200 and ctype.startswith("image/") and len(r.content) > 1000
        return ok, f"HTTP {r.status_code} {ctype} {len(r.content)} bytes"
    except Exception as exc:
        return False, str(exc)


def main() -> None:
    state = load_state()
    blog_id = core.env("BLOGGER_BLOG_ID")
    access = core.token()
    core.blog_check(access, blog_id)

    report = {"at": core.now_iso(), "total": 0, "updated": 0, "verified": 0, "failed": []}

    for skey, story in sorted(state.get("stories", {}).items()):
        post_id = str(story.get("post_id", "")).strip()
        if not post_id:
            continue
        report["total"] += 1

        post = core.blogger("GET", f"blogs/{blog_id}/posts/{post_id}", access)
        title = str(post.get("title") or story.get("title") or "EdgeAI report")
        labels = post.get("labels") or []
        source = str((story.get("trust") or {}).get("source") or "EdgeAI")
        image_url = ensure_story_art(skey, title, source, labels)

        cdn_ok, cdn_detail = verify_cdn(image_url)
        if not cdn_ok:
            report["failed"].append({"story": skey, "stage": "cdn", "detail": cdn_detail, "url": image_url})
            print(f"CDN FAIL: {skey}: {cdn_detail}")
            continue

        content = clean_old_hero(str(post.get("content", "")))
        new_content = hero_html(image_url, title) + content
        payload = {
            "kind": "blogger#post",
            "title": title,
            "content": new_content,
            "labels": labels,
        }
        core.blogger("PUT", f"blogs/{blog_id}/posts/{post_id}", access, payload)
        report["updated"] += 1

        stored = core.blogger("GET", f"blogs/{blog_id}/posts/{post_id}", access)
        stored_content = str(stored.get("content", ""))
        verified = image_url in stored_content and 'edge-article-hero' in stored_content and '<img' in stored_content.lower()
        if verified:
            report["verified"] += 1
            story["image_url"] = image_url
            story["image_source"] = "EdgeAI editorial artwork"
            story["image_verified_in_blogger"] = True
            story["last_visual_refresh"] = core.now_iso()
            print(f"IMAGE VERIFIED: {title} -> {image_url}")
        else:
            story["image_verified_in_blogger"] = False
            report["failed"].append({"story": skey, "stage": "blogger_get", "url": image_url})
            print(f"BLOGGER VERIFY FAIL: {title}")

    state["last_image_repair"] = {
        "at": report["at"],
        "total": report["total"],
        "updated": report["updated"],
        "verified": report["verified"],
        "failed": len(report["failed"]),
    }
    save_state(state)
    REPORT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"IMAGE REPAIR COMPLETE: total={report['total']} updated={report['updated']} verified={report['verified']} failed={len(report['failed'])}")
    if report["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
