#!/usr/bin/env python3
from __future__ import annotations

import argparse
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
SOURCE_MARKER = "/assets/source-media/"


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


def hero_html(url: str, title: str, attribution: str) -> str:
    return (
        '<figure class="edge-article-hero" style="margin:0 0 22px 0;">'
        f'<img src="{html.escape(url, quote=True)}" alt="{html.escape(title, quote=True)}" '
        'loading="eager" style="display:block;width:100%;height:auto;max-height:560px;object-fit:cover;'
        'border-radius:14px;border:1px solid #303846;background:#11161e;" />'
        '<figcaption style="margin-top:7px;font:11px/1.4 Arial,sans-serif;color:#8792a0;">'
        f'Image: {html.escape(attribution)}</figcaption></figure>'
    )


def verify_remote_image(url: str) -> tuple[bool, str]:
    try:
        r = requests.get(url, timeout=25, headers={"User-Agent": core.USER_AGENT})
        ctype = r.headers.get("content-type", "").lower()
        ok = r.status_code == 200 and ctype.startswith("image/") and len(r.content) > 5000
        return ok, f"HTTP {r.status_code} {ctype} {len(r.content)} bytes"
    except Exception as exc:
        return False, str(exc)


def verify_local_or_remote(url: str) -> tuple[bool, str]:
    if SOURCE_MARKER in url:
        name = url.rsplit("/", 1)[-1]
        path = ROOT / "assets" / "source-media" / name
        if path.exists() and path.stat().st_size > 5000:
            return True, f"local mirrored source image {path.stat().st_size} bytes"
    return verify_remote_image(url)


def repair() -> None:
    state = load_state()
    blog_id = core.env("BLOGGER_BLOG_ID")
    access = core.token()
    core.blog_check(access, blog_id)

    report = {
        "at": core.now_iso(),
        "mode": "repair",
        "total": 0,
        "updated": 0,
        "verified_in_blogger": 0,
        "real_source_images": 0,
        "fallback_images": 0,
        "failed": [],
    }

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
        is_real = SOURCE_MARKER in image_url
        attribution = source if is_real else "EdgeAI editorial artwork"

        asset_ok, asset_detail = verify_local_or_remote(image_url)
        if not asset_ok:
            report["failed"].append({"story": skey, "stage": "asset", "detail": asset_detail, "url": image_url})
            print(f"IMAGE ASSET FAIL: {skey}: {asset_detail}")
            continue

        content = clean_old_hero(str(post.get("content", "")))
        payload = {
            "kind": "blogger#post",
            "title": title,
            "content": hero_html(image_url, title, attribution) + content,
            "labels": labels,
        }
        core.blogger("PUT", f"blogs/{blog_id}/posts/{post_id}", access, payload)
        report["updated"] += 1

        stored = core.blogger("GET", f"blogs/{blog_id}/posts/{post_id}", access)
        stored_content = str(stored.get("content", ""))
        verified = image_url in stored_content and 'edge-article-hero' in stored_content and '<img' in stored_content.lower()
        if verified:
            report["verified_in_blogger"] += 1
            if is_real:
                report["real_source_images"] += 1
            else:
                report["fallback_images"] += 1
            story["image_url"] = image_url
            story["image_source"] = attribution
            story["image_kind"] = "mirrored_source" if is_real else "editorial_fallback"
            story["image_verified_in_blogger"] = True
            story["last_visual_refresh"] = core.now_iso()
            print(f"IMAGE STORED: {title} -> {image_url} [{story['image_kind']}]")
        else:
            story["image_verified_in_blogger"] = False
            report["failed"].append({"story": skey, "stage": "blogger_get", "url": image_url})
            print(f"BLOGGER VERIFY FAIL: {title}")

    state["last_image_repair"] = {
        "at": report["at"],
        "total": report["total"],
        "updated": report["updated"],
        "verified": report["verified_in_blogger"],
        "real_source_images": report["real_source_images"],
        "fallback_images": report["fallback_images"],
        "failed": len(report["failed"]),
    }
    save_state(state)
    REPORT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        "IMAGE REPAIR COMPLETE: "
        f"total={report['total']} updated={report['updated']} stored={report['verified_in_blogger']} "
        f"real={report['real_source_images']} fallback={report['fallback_images']} failed={len(report['failed'])}"
    )
    if report["failed"]:
        raise SystemExit(1)


def verify_only() -> None:
    state = load_state()
    blog_id = core.env("BLOGGER_BLOG_ID")
    access = core.token()
    core.blog_check(access, blog_id)

    report = {
        "at": core.now_iso(),
        "mode": "verify",
        "total": 0,
        "cdn_verified": 0,
        "blogger_verified": 0,
        "real_source_images": 0,
        "fallback_images": 0,
        "failed": [],
    }

    for skey, story in sorted(state.get("stories", {}).items()):
        post_id = str(story.get("post_id", "")).strip()
        image_url = str(story.get("image_url", "")).strip()
        if not post_id or not image_url:
            continue
        report["total"] += 1
        is_real = SOURCE_MARKER in image_url
        report["real_source_images" if is_real else "fallback_images"] += 1

        cdn_ok, cdn_detail = verify_remote_image(image_url)
        if cdn_ok:
            report["cdn_verified"] += 1
        else:
            report["failed"].append({"story": skey, "stage": "cdn_after_commit", "detail": cdn_detail, "url": image_url})

        post = core.blogger("GET", f"blogs/{blog_id}/posts/{post_id}", access)
        stored_content = str(post.get("content", ""))
        if image_url in stored_content and '<img' in stored_content.lower():
            report["blogger_verified"] += 1
        else:
            report["failed"].append({"story": skey, "stage": "blogger_after_commit", "url": image_url})

        print(f"FINAL IMAGE VERIFY: {story.get('title', skey)} -> cdn={cdn_ok} kind={'source' if is_real else 'fallback'}")

    REPORT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        "FINAL IMAGE VERIFY COMPLETE: "
        f"total={report['total']} cdn={report['cdn_verified']} blogger={report['blogger_verified']} "
        f"real={report['real_source_images']} fallback={report['fallback_images']} failed={len(report['failed'])}"
    )
    if report["failed"]:
        raise SystemExit(1)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    if args.verify_only:
        verify_only()
    else:
        repair()


if __name__ == "__main__":
    main()
