#!/usr/bin/env python3
"""Central EdgeAI editor/publisher.

This is the only scheduled runner allowed to call Gemini or write Blogger posts.
Discovery runners only feed queue_fast.json and queue_deep.json.
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

import edgeai as core

ROOT = Path(__file__).resolve().parent
QUEUE_PATHS = (ROOT / "queue_fast.json", ROOT / "queue_deep.json")
STATE_PATH = ROOT / "editor_state.json"
CONFIG_PATH = ROOT / "bootstrap_config.json"
NORMAL_FRESH_HOURS = 72
FALLBACK_IMAGE = "https://raw.githubusercontent.com/BoomForge/EdgeAI/main/assets/edgeai-newsroom-fallback.svg"


def load(path: Path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def save(path: Path, data) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def config():
    return load(CONFIG_PATH, {
        "enabled": True,
        "target_articles": 30,
        "max_evaluations_per_bootstrap_run": 6,
        "max_publications_per_bootstrap_run": 3,
        "max_evaluations_per_live_run": 5,
        "max_publications_per_live_run": 2,
    })


def queues() -> list[dict]:
    merged = {}
    for path in QUEUE_PATHS:
        data = load(path, {"candidates": []})
        for item in data.get("candidates", []):
            candidate_id = item.get("candidate_id") or core.cid(item.get("url", ""))
            if not candidate_id:
                continue
            item["candidate_id"] = candidate_id
            old = merged.get(candidate_id)
            if old is None or int(item.get("priority", 2)) < int(old.get("priority", 2)):
                merged[candidate_id] = item
    return list(merged.values())


def item_time(item: dict):
    return core.parse_date(item.get("published", "")) or core.parse_date(item.get("discovered_at", "")) or datetime(1970, 1, 1, tzinfo=timezone.utc)


def rank(item: dict):
    return (
        int(item.get("priority", 2)),
        -int(item.get("search_score", 0)),
        -item_time(item).timestamp(),
    )


def bootstrap_active(state: dict, cfg: dict) -> bool:
    boot = state.setdefault("bootstrap", {
        "target": int(cfg.get("target_articles", 30)),
        "published": 0,
        "complete": not bool(cfg.get("enabled", True)),
        "started_at": core.now_iso(),
    })
    boot.setdefault("started_at", core.now_iso())
    boot.setdefault("published", 0)
    boot.setdefault("complete", not bool(cfg.get("enabled", True)))
    boot["target"] = int(cfg.get("target_articles", boot.get("target", 30)))
    if int(boot.get("published", 0)) >= int(boot.get("target", 30)):
        boot["complete"] = True
    return bool(cfg.get("enabled", True)) and not bool(boot.get("complete", False))


def eligible(items: list[dict], state: dict, bootstrap: bool) -> list[dict]:
    processed = state.setdefault("processed", {})
    cutoff = datetime.now(timezone.utc) - timedelta(hours=NORMAL_FRESH_HOURS)
    out = []
    for item in items:
        cid = item["candidate_id"]
        if cid in processed:
            continue
        if bootstrap:
            if item.get("bootstrap"):
                out.append(item)
        else:
            if item_time(item) >= cutoff:
                out.append(item)
            else:
                processed[cid] = {"status": "expired", "url": item.get("url", ""), "at": core.now_iso()}
    return sorted(out, key=rank)


def add_featured(labels: list[str], score: int) -> list[str]:
    if score < 90 or "Featured" in labels:
        return labels
    if len(labels) < 8:
        return labels + ["Featured"]
    return labels[:7] + ["Featured"]


def quota_limited(exc: Exception) -> bool:
    response = getattr(exc, "response", None)
    status = getattr(response, "status_code", None)
    if status == 429:
        return True
    text = str(exc).lower()
    return "quota" in text and ("exceed" in text or "limit" in text or "resource exhausted" in text)


def trust_label(score: int) -> str:
    if score >= 90:
        return "Verified"
    if score >= 75:
        return "Strong"
    if score >= 60:
        return "Reasonable"
    if score >= 40:
        return "Caution"
    return "Low confidence"


def trust_rating(item: dict, status: str) -> tuple[int, str, str]:
    """Rate evidence confidence for this report, not the permanent reputation of a source."""
    priority = max(1, min(4, int(item.get("priority", 2))))
    kind = str(item.get("kind", "")).lower()
    source = str(item.get("source_name", "")).lower()
    summary = core.clean_text(item.get("summary", ""))

    score = {1: 84, 2: 74, 3: 62, 4: 50}[priority]

    if "primary" in kind:
        score += 8
    elif "research" in kind:
        score += 5
    elif "independent" in kind:
        score += 3

    if any(token in kind for token in ("signal", "discovery", "directory")):
        score -= 8
    if any(token in source for token in ("futuretools", "futurepedia", "product hunt")):
        score -= 10

    score += {
        "CONFIRMED": 6,
        "DEVELOPING": -2,
        "EARLY SIGNAL": -12,
        "RUMOUR": -28,
    }.get(status, -8)

    if len(summary) >= 200:
        score += 3
    elif len(summary) >= 80:
        score += 1
    else:
        score -= 4

    score += 2 if item.get("published") else -2

    age = datetime.now(timezone.utc) - item_time(item)
    if age <= timedelta(hours=24):
        score += 3
    elif age <= timedelta(hours=72):
        score += 1
    elif age > timedelta(days=7):
        score -= 4

    caps = {"CONFIRMED": 96, "DEVELOPING": 84, "EARLY SIGNAL": 68, "RUMOUR": 42}
    score = max(15, min(caps.get(status, 68), score))
    label = trust_label(score)

    if status == "CONFIRMED" and priority == 1:
        reason = "Confirmed information from a high-authority source with directly traceable source material."
    elif status == "CONFIRMED":
        reason = "The central claim is confirmed, with source authority and traceability reflected in this score."
    elif status == "DEVELOPING":
        reason = "The development appears real, but some details are still arriving or remain incomplete."
    elif status == "EARLY SIGNAL":
        reason = "There is a credible signal, but the available evidence is not yet complete enough for high confidence."
    else:
        reason = "The information remains weakly verified or uncertain and should be treated cautiously."

    if any(token in source for token in ("futuretools", "futurepedia", "product hunt")):
        reason += " This item originated from a discovery source, which lowers confidence until primary evidence is available."

    return score, label, reason


def trust_card(score: int, label: str, reason: str, source_name: str) -> str:
    if score >= 90:
        color = "#7ce0b6"
    elif score >= 75:
        color = "#9fc7ff"
    elif score >= 60:
        color = "#e7c47a"
    elif score >= 40:
        color = "#e99a68"
    else:
        color = "#e87682"

    safe_label = html.escape(label)
    safe_reason = html.escape(reason)
    safe_source = html.escape(source_name)
    return f"""
<div class="edge-trust-card" data-trust-score="{score}" data-trust-label="{safe_label}" style="display:flex;align-items:center;gap:14px;margin:0 0 22px;padding:14px 16px;border:1px solid #303846;border-radius:14px;background:#141922;color:#eef2f7;">
  <div role="img" aria-label="Evidence Trust {score} out of 100" title="Evidence Trust {score}/100" style="width:62px;height:62px;min-width:62px;border-radius:50%;padding:5px;background:conic-gradient({color} 0 {score}%,#2a303b {score}% 100%);">
    <div style="width:52px;height:52px;border-radius:50%;background:#0e1218;display:flex;align-items:center;justify-content:center;font:800 17px Arial,sans-serif;color:{color};">{score}</div>
  </div>
  <div style="min-width:0;">
    <div style="font:800 11px Arial,sans-serif;letter-spacing:1px;text-transform:uppercase;color:#9ca8b7;">Evidence Trust · {safe_source}</div>
    <div style="font:800 17px Arial,sans-serif;color:{color};margin:2px 0 3px;">{safe_label}</div>
    <div style="font:13px/1.45 Arial,sans-serif;color:#d2d9e2;">{safe_reason}</div>
    <div style="font:11px/1.4 Arial,sans-serif;color:#8f99a6;margin-top:5px;">Evidence confidence for this report, not a permanent rating of the company or site.</div>
  </div>
</div>
""".strip()


def _image_candidate_ok(url: str) -> bool:
    if not url:
        return False
    lower = url.lower()
    if not lower.startswith(("http://", "https://")):
        return False
    bad = (
        "favicon", "avatar", "logo-small", "icon-", "sprite", "emoji", "badge",
        "placeholder", "%3clink", "%3cimage", "<link", "<image", "opengraph,%20twitter-cards",
        "opengraph%2c%20twitter-cards", "path%20of%20image", "your-image", "example.com/image",
    )
    return not any(token in lower for token in bad)


def extract_source_image(item: dict) -> tuple[str, str]:
    """Return the strongest editorial image we can find plus an attribution label."""
    if _image_candidate_ok(str(item.get("image_url", ""))):
        return str(item["image_url"]), str(item.get("source_name", "Source"))

    url = str(item.get("url", "")).strip()
    if not url:
        return FALLBACK_IMAGE, "EdgeAI"

    try:
        response = requests.get(
            url,
            timeout=core.TIMEOUT,
            headers={
                "User-Agent": core.USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
            },
        )
        response.raise_for_status()
        if "html" not in response.headers.get("content-type", "").lower():
            return FALLBACK_IMAGE, "EdgeAI"

        soup = BeautifulSoup(response.text, "html.parser")
        candidates: list[str] = []

        selectors = (
            ("meta", {"property": "og:image"}),
            ("meta", {"property": "og:image:secure_url"}),
            ("meta", {"name": "twitter:image"}),
            ("meta", {"property": "twitter:image"}),
            ("link", {"rel": "image_src"}),
        )
        for tag, attrs in selectors:
            node = soup.find(tag, attrs=attrs)
            if not node:
                continue
            value = node.get("content") or node.get("href")
            if value:
                candidates.append(str(value))

        for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
            raw = script.string or script.get_text(" ", strip=True)
            if not raw or '"image"' not in raw:
                continue
            try:
                data = json.loads(raw)
            except Exception:
                continue
            stack = data if isinstance(data, list) else [data]
            for obj in stack:
                if not isinstance(obj, dict):
                    continue
                image = obj.get("image")
                if isinstance(image, str):
                    candidates.append(image)
                elif isinstance(image, list):
                    candidates.extend(str(x) for x in image if isinstance(x, str))
                elif isinstance(image, dict):
                    value = image.get("url") or image.get("contentUrl")
                    if value:
                        candidates.append(str(value))

        for selector in ("article img", "main img", ".post img", ".article img"):
            for node in soup.select(selector)[:8]:
                value = node.get("src") or node.get("data-src") or node.get("data-lazy-src")
                if value:
                    width = str(node.get("width", "")).strip()
                    height = str(node.get("height", "")).strip()
                    try:
                        if width and height and int(width) < 300 and int(height) < 160:
                            continue
                    except ValueError:
                        pass
                    candidates.append(str(value))

        for candidate in candidates:
            candidate = urljoin(url, html.unescape(candidate.strip()))
            if _image_candidate_ok(candidate):
                return candidate, str(item.get("source_name", "Source"))
    except Exception as exc:
        print(f"Image discovery warning - {item.get('source_name', 'source')}: {exc}")

    return FALLBACK_IMAGE, "EdgeAI"


def hero_media(image_url: str, attribution: str, title: str) -> str:
    safe_url = html.escape(image_url, quote=True)
    safe_attr = html.escape(attribution)
    safe_title = html.escape(title)
    fallback = html.escape(FALLBACK_IMAGE, quote=True)
    return f"""
<figure class="edge-article-hero" style="margin:0 0 22px;">
  <img src="{safe_url}" alt="{safe_title}" loading="eager" referrerpolicy="no-referrer" onerror="this.onerror=null;this.src='{fallback}';" style="display:block;width:100%;max-height:560px;object-fit:cover;border-radius:16px;border:1px solid #303846;background:#11161e;" />
  <figcaption style="margin-top:7px;font:11px/1.4 Arial,sans-serif;color:#8792a0;">Image: {safe_attr}</figcaption>
</figure>
""".strip()


def find_queue_item(source_url: str, source_name: str = "") -> dict:
    for item in queues():
        if item.get("url") == source_url:
            return item
    return {
        "url": source_url,
        "source_name": source_name or (urlparse(source_url).netloc if source_url else "Source"),
        "priority": 2,
        "kind": "primary",
        "summary": "",
        "published": "",
        "title": "",
    }


def publish_candidate(item: dict, state: dict, key: str, blog_id: str, access: str):
    decision = core.ask_editor(item, key)
    score = int(decision.get("score", 0))
    should_publish = bool(decision.get("publish")) and score >= 75
    status = str(decision.get("status", "DEVELOPING")).upper()
    if status not in {"CONFIRMED", "DEVELOPING", "EARLY SIGNAL", "RUMOUR"}:
        status = "DEVELOPING"
    skey = core.story_key(str(decision.get("story_key", "")), str(decision.get("title") or item["title"]))

    if not should_publish:
        return "ignored", score, skey, str(decision.get("reason", ""))[:500], False, None

    existing_story = state.setdefault("stories", {}).get(skey)
    existing_post = None
    if existing_story and existing_story.get("post_id"):
        existing_post = core.blogger("GET", f"blogs/{blog_id}/posts/{existing_story['post_id']}", access)
        decision = core.ask_editor(item, key, existing_post)
        score = int(decision.get("score", score))
        if not bool(decision.get("publish", True)) or score < 75:
            return "ignored_update", score, skey, str(decision.get("reason", ""))[:500], False, None
        status = str(decision.get("status", status)).upper()
        if status not in {"CONFIRMED", "DEVELOPING", "EARLY SIGNAL", "RUMOUR"}:
            status = "DEVELOPING"

    title = str(decision.get("title") or item["title"]).strip()[:160]
    body = str(decision.get("body_html", "")).strip()
    if len(core.clean_text(body)) < 180:
        raise RuntimeError("Generated body too short; refusing to publish")

    trust_score, trust_name, trust_reason = trust_rating(item, status)
    trust = {
        "score": trust_score,
        "label": trust_name,
        "reason": trust_reason,
        "source": item.get("source_name", ""),
    }
    image_url, image_source = extract_source_image(item)
    body = (
        hero_media(image_url, image_source, title)
        + trust_card(trust_score, trust_name, trust_reason, str(item.get("source_name", "Source")))
        + body
    )

    labels = add_featured(core.safe_labels(decision.get("labels"), status), score)
    payload = {
        "kind": "blogger#post",
        "title": title,
        "content": body + core.footer(item, status),
        "labels": labels,
    }

    if existing_post:
        post = core.blogger("PUT", f"blogs/{blog_id}/posts/{existing_post['id']}", access, payload)
        action = "updated"
        is_new = False
    else:
        post = core.blogger("POST", f"blogs/{blog_id}/posts", access, payload)
        action = "published"
        is_new = True

    story = state.setdefault("stories", {}).setdefault(skey, {})
    source_urls = list(dict.fromkeys([*(story.get("source_urls") or []), item["url"]]))[-12:]
    story.update({
        "title": title,
        "post_id": str(post.get("id", "")),
        "post_url": post.get("url", ""),
        "status": status,
        "score": score,
        "trust": trust,
        "image_url": image_url,
        "image_source": image_source,
        "source_urls": source_urls,
        "last_updated": core.now_iso(),
    })
    return action, score, skey, post.get("url", ""), is_new, trust


def visual_backfill(state: dict, blog_id: str, access: str) -> None:
    """Add hero imagery to existing live stories without re-running Gemini."""
    updated = skipped = 0
    for skey, story in state.setdefault("stories", {}).items():
        post_id = str(story.get("post_id", "")).strip()
        source_urls = story.get("source_urls") or []
        if not post_id or not source_urls:
            skipped += 1
            continue

        post = core.blogger("GET", f"blogs/{blog_id}/posts/{post_id}", access)
        content = str(post.get("content", ""))
        # Visual mode is a repair pass: remove any previous hero block so a bad
        # placeholder/fallback can be replaced with newly discovered source art.
        content = re.sub(
            r'<figure class="edge-article-hero"[\s\S]*?</figure>\s*',
            '',
            content,
            count=1,
            flags=re.IGNORECASE,
        )

        item = find_queue_item(str(source_urls[-1]), str(story.get("trust", {}).get("source", "")))
        item["title"] = story.get("title", item.get("title", ""))
        image_url, image_source = extract_source_image(item)
        title = str(post.get("title") or story.get("title") or "EdgeAI report")
        payload = {
            "kind": "blogger#post",
            "title": title,
            "content": hero_media(image_url, image_source, title) + content,
            "labels": post.get("labels", []),
        }
        result = core.blogger("PUT", f"blogs/{blog_id}/posts/{post_id}", access, payload)
        story["image_url"] = image_url
        story["image_source"] = image_source
        story["post_url"] = result.get("url", story.get("post_url", ""))
        story["last_visual_refresh"] = core.now_iso()
        updated += 1
        print(f"VISUAL BACKFILL: {title} -> {image_url}")

    state["last_visual_backfill"] = {
        "at": core.now_iso(),
        "updated": updated,
        "skipped": skipped,
    }
    save(STATE_PATH, state)
    print(f"VISUAL BACKFILL COMPLETE: updated={updated}; skipped={skipped}.")


def check() -> None:
    key = core.env("GEMINI_API_KEY")
    result = core.gemini('Return JSON only: {"ok": true}.', key)
    if result.get("ok") is not True:
        raise RuntimeError(f"Gemini check failed: {result}")
    access = core.token()
    blog = core.blog_check(access, core.env("BLOGGER_BLOG_ID"))
    q = queues()
    print(f"Gemini: OK ({core.MODEL})")
    print(f"Blogger: OK ({blog.get('name')} - {blog.get('url')})")
    print(f"Queues: OK ({len(q)} combined candidates). Nothing published.")


def run(mode: str) -> None:
    cfg = config()
    state = load(STATE_PATH, {"version": 2, "processed": {}, "stories": {}, "errors": {}})
    state.setdefault("processed", {})
    state.setdefault("stories", {})
    state.setdefault("errors", {})

    blog_id = core.env("BLOGGER_BLOG_ID")
    access = core.token()
    core.blog_check(access, blog_id)

    if mode == "visual":
        visual_backfill(state, blog_id, access)
        return

    active = bootstrap_active(state, cfg)
    if mode == "live":
        active = False
    elif mode == "bootstrap":
        active = True

    items = queues()
    pool = eligible(items, state, active)
    if active and not pool:
        state["bootstrap"]["complete"] = True
        state["bootstrap"]["completed_at"] = core.now_iso()
        active = False
        pool = eligible(items, state, False)

    eval_cap = int(cfg.get("max_evaluations_per_bootstrap_run", 6) if active else cfg.get("max_evaluations_per_live_run", 5))
    publish_cap = int(cfg.get("max_publications_per_bootstrap_run", 3) if active else cfg.get("max_publications_per_live_run", 2))
    key = core.env("GEMINI_API_KEY")

    evaluated = published_actions = new_posts = 0
    quota_paused = False
    for item in pool[:eval_cap]:
        if published_actions >= publish_cap:
            break
        candidate_id = item["candidate_id"]
        try:
            action, score, skey, detail, is_new, trust = publish_candidate(item, state, key, blog_id, access)
            evaluated += 1
            processed = {
                "url": item.get("url", ""), "status": action, "score": score,
                "story_key": skey, "at": core.now_iso(), "bootstrap": bool(item.get("bootstrap")),
            }
            if trust:
                processed["trust"] = trust
            state["processed"][candidate_id] = processed
            if action in {"published", "updated"}:
                published_actions += 1
                if is_new:
                    new_posts += 1
                    if active:
                        state["bootstrap"]["published"] = int(state["bootstrap"].get("published", 0)) + 1
                trust_text = f" · trust {trust['score']}/100 {trust['label']}" if trust else ""
                print(f"{action.upper()} {score}{trust_text}: {detail}")
            else:
                print(f"IGNORED {score}: {item.get('title', '')}")
        except Exception as exc:
            if quota_limited(exc):
                quota_paused = True
                state["last_quota_pause"] = {"at": core.now_iso(), "candidate_id": candidate_id}
                print("FREE-TIER QUOTA REACHED: stopping cleanly; candidate remains unprocessed for a later run.")
                break
            errors = state["errors"].setdefault(candidate_id, {"count": 0})
            errors["count"] = int(errors.get("count", 0)) + 1
            errors["last_error"] = str(exc)[:500]
            errors["at"] = core.now_iso()
            print(f"Candidate error - {item.get('title', '')}: {exc}", file=sys.stderr)
            if errors["count"] >= 3:
                state["processed"][candidate_id] = {
                    "url": item.get("url", ""), "status": "error_after_3_attempts", "at": core.now_iso()
                }

        if active and int(state["bootstrap"].get("published", 0)) >= int(state["bootstrap"].get("target", 30)):
            state["bootstrap"]["complete"] = True
            state["bootstrap"]["completed_at"] = core.now_iso()
            break

    if active and not state["bootstrap"].get("complete") and not quota_paused:
        remaining_bootstrap = [i for i in eligible(items, state, True)]
        if not remaining_bootstrap:
            state["bootstrap"]["complete"] = True
            state["bootstrap"]["completed_at"] = core.now_iso()

    state["last_run"] = {
        "at": core.now_iso(), "mode": "bootstrap" if active else "live",
        "eligible": len(pool), "evaluated": evaluated,
        "publish_actions": published_actions, "new_posts": new_posts,
        "quota_paused": quota_paused,
    }
    save(STATE_PATH, state)
    boot = state.get("bootstrap", {})
    print(
        f"EDITOR COMPLETE: mode={'bootstrap' if active else 'live'}; evaluated={evaluated}; "
        f"publish_actions={published_actions}; bootstrap_posts={boot.get('published', 0)}/{boot.get('target', 30)}; "
        f"bootstrap_complete={boot.get('complete', False)}; quota_paused={quota_paused}."
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("check", "auto", "bootstrap", "live", "visual"), default="check")
    args = parser.parse_args()
    if args.mode == "check":
        check()
    else:
        run(args.mode)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"FATAL: {exc}", file=sys.stderr)
        raise SystemExit(1)
