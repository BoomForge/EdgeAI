#!/usr/bin/env python3
"""Free, unattended distribution for EdgeAI Blogger articles.

The publisher writes canonical Blogger URLs into editor_state.json. This script
fans new or updated articles out through account-free update services and
Blogger's WebSub feed, while keeping a small state file so successful services
are never spammed repeatedly.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
from xmlrpc.client import Fault, ProtocolError, dumps, loads

import requests

ROOT = Path(__file__).resolve().parent
EDITOR_STATE = ROOT / "editor_state.json"
DISTRIBUTION_STATE = ROOT / "distribution_state.json"
BLOG_NAME = "EdgeAI News"
BLOG_URL = "https://edgeainews.blogspot.com/"
BLOG_HOST = "edgeainews.blogspot.com"
ATOM_URL = BLOG_URL + "feeds/posts/default"
RSS_URL = BLOG_URL + "feeds/posts/default?alt=rss"
SITEMAP_URL = BLOG_URL + "sitemap.xml"
ROBOTS_URL = BLOG_URL + "robots.txt"
TIMEOUT = 30
DEFAULT_LIMIT = 12
USER_AGENT = "EdgeAI-Distribution/1.0 (+https://edgeainews.blogspot.com/)"

# These are account-free publisher/update endpoints. Ping-O-Matic fans a blog
# update out to its maintained downstream services; Twingly is also a current
# WordPress-listed update service.
XMLRPC_SERVICES = {
    "pingomatic": "https://rpc.pingomatic.com/",
    "twingly": "https://rpc.twingly.com/",
}

# Blogger feeds support WebSub/PubSubHubbub. Publishing the Atom topic to
# multiple free hubs makes new entries available to subscribed readers and
# aggregators without waiting for polling.
WEBSUB_HUBS = {
    "google-websub": ("https://pubsubhubbub.appspot.com/", "hub.url"),
    "websubhub": ("https://websubhub.com/hub", "hub.topic"),
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load(path: Path, default):
    if not path.exists():
        return default
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default
    return data if isinstance(data, type(default)) else default


def save(path: Path, data) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def canonical_article_url(value: str) -> str:
    value = str(value or "").strip()
    if not value:
        return ""
    try:
        parts = urlsplit(value)
    except ValueError:
        return ""
    if parts.scheme != "https" or (parts.hostname or "").lower() != BLOG_HOST:
        return ""
    path = parts.path or "/"
    if not path.endswith(".html"):
        return ""
    return urlunsplit(("https", BLOG_HOST, path, "", ""))


def story_stamp(story: dict) -> str:
    for key in ("last_updated", "last_visual_refresh", "post_id"):
        value = str(story.get(key, "")).strip()
        if value:
            return value
    return "published"


def published_articles(editor_state: dict) -> list[dict]:
    out: list[dict] = []
    for story_key, story in (editor_state.get("stories") or {}).items():
        if not isinstance(story, dict):
            continue
        url = canonical_article_url(story.get("post_url", ""))
        if not url:
            continue
        out.append({
            "story_key": str(story_key),
            "title": str(story.get("title") or "EdgeAI report").strip(),
            "url": url,
            "stamp": story_stamp(story),
        })
    out.sort(key=lambda item: (item["stamp"], item["url"]), reverse=True)
    return out


def requests_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT, "Accept": "*/*"})
    return session


def xmlrpc_extended_ping(session: requests.Session, endpoint: str, article_url: str) -> str:
    body = dumps(
        (BLOG_NAME, BLOG_URL, article_url, RSS_URL),
        methodname="weblogUpdates.extendedPing",
        allow_none=False,
    )
    response = session.post(
        endpoint,
        data=body.encode("utf-8"),
        headers={"Content-Type": "text/xml"},
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    try:
        values, _ = loads(response.content)
    except (Fault, ProtocolError, ValueError) as exc:
        raise RuntimeError(f"invalid XML-RPC response: {exc}") from exc
    if not values:
        return "accepted"
    result = values[0]
    if isinstance(result, dict):
        if result.get("flerror") in (True, 1, "1"):
            raise RuntimeError(str(result.get("message") or "service rejected ping"))
        return str(result.get("message") or "accepted")[:200]
    return str(result)[:200]


def websub_publish(session: requests.Session, endpoint: str, topic_field: str) -> str:
    response = session.post(
        endpoint,
        data={"hub.mode": "publish", topic_field: ATOM_URL},
        timeout=TIMEOUT,
        allow_redirects=True,
    )
    if response.status_code < 200 or response.status_code >= 300:
        raise RuntimeError(f"HTTP {response.status_code}: {response.text[:160]}")
    return f"HTTP {response.status_code}"


def fetch_text(session: requests.Session, url: str) -> tuple[int, str]:
    response = session.get(url, timeout=TIMEOUT, allow_redirects=True)
    return response.status_code, response.text


def discovery_health(session: requests.Session, article_urls: list[str]) -> list[str]:
    """Audit the native Blogger discovery surfaces used by normal crawlers."""
    notes: list[str] = []
    try:
        status, sitemap = fetch_text(session, SITEMAP_URL)
        if status == 200:
            present = sum(1 for url in article_urls if url in sitemap)
            notes.append(
                f"Blogger sitemap HTTP 200; {present}/{len(article_urls)} tracked article URL(s) present"
            )
        else:
            notes.append(f"Blogger sitemap HTTP {status}")
    except Exception as exc:
        notes.append(f"Blogger sitemap check warning: {exc}")

    try:
        status, robots = fetch_text(session, ROBOTS_URL)
        advertised = "sitemap" in robots.lower()
        notes.append(f"robots.txt HTTP {status}; sitemap advertised={advertised}")
    except Exception as exc:
        notes.append(f"robots.txt check warning: {exc}")

    try:
        status, _ = fetch_text(session, ATOM_URL)
        notes.append(f"Blogger Atom feed HTTP {status}")
    except Exception as exc:
        notes.append(f"Blogger Atom feed check warning: {exc}")
    return notes


def write_summary(lines: list[str]) -> None:
    target = os.environ.get("GITHUB_STEP_SUMMARY", "").strip()
    if not target:
        return
    with open(target, "a", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Distribute new/updated EdgeAI Blogger articles for free.")
    parser.add_argument("--state", default=str(DISTRIBUTION_STATE))
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    editor_state = load(EDITOR_STATE, {})
    articles = published_articles(editor_state)
    if not articles:
        print("No published Blogger article URLs found in editor_state.json.")
        return 0

    state_path = Path(args.state)
    state = load(state_path, {"version": 1, "articles": {}, "feed": {}})
    state.setdefault("version", 1)
    state.setdefault("articles", {})
    state.setdefault("feed", {})

    pending: list[dict] = []
    for article in articles:
        saved = state["articles"].get(article["url"], {})
        service_stamps = saved.get("services", {}) if isinstance(saved, dict) else {}
        needed = [name for name in XMLRPC_SERVICES if service_stamps.get(name) != article["stamp"]]
        if needed:
            pending.append({**article, "needed": needed})

    pending = pending[: max(1, args.limit)]
    newest_stamp = max((article["stamp"] for article in articles), default="")
    feed_needed = any(state["feed"].get(name) != newest_stamp for name in WEBSUB_HUBS)

    print(f"Tracked Blogger articles: {len(articles)}")
    print(f"Article update pings pending this run: {len(pending)}")
    print(f"Feed WebSub refresh pending: {feed_needed}")

    if args.dry_run:
        for article in pending:
            print(f"DRY RUN: {article['url']} -> {', '.join(article['needed'])}")
        if feed_needed:
            print(f"DRY RUN: {ATOM_URL} -> {', '.join(WEBSUB_HUBS)}")
        return 0

    session = requests_session()
    failures: list[str] = []
    successes = 0

    for article in pending:
        entry = state["articles"].setdefault(
            article["url"], {"title": article["title"], "services": {}}
        )
        entry["title"] = article["title"]
        entry.setdefault("services", {})
        for service in article["needed"]:
            endpoint = XMLRPC_SERVICES[service]
            try:
                detail = xmlrpc_extended_ping(session, endpoint, article["url"])
                entry["services"][service] = article["stamp"]
                entry[f"{service}_at"] = now_iso()
                entry[f"{service}_detail"] = detail
                successes += 1
                print(f"{service}: {article['url']} -> {detail}")
            except Exception as exc:
                message = f"{service} failed for {article['url']}: {exc}"
                failures.append(message)
                print(f"WARNING: {message}", file=sys.stderr)

    if feed_needed:
        for service, (endpoint, topic_field) in WEBSUB_HUBS.items():
            if state["feed"].get(service) == newest_stamp:
                continue
            try:
                detail = websub_publish(session, endpoint, topic_field)
                state["feed"][service] = newest_stamp
                state["feed"][f"{service}_at"] = now_iso()
                state["feed"][f"{service}_detail"] = detail
                successes += 1
                print(f"{service}: {ATOM_URL} -> {detail}")
            except Exception as exc:
                message = f"{service} failed for {ATOM_URL}: {exc}"
                failures.append(message)
                print(f"WARNING: {message}", file=sys.stderr)

    health = discovery_health(session, [article["url"] for article in articles[:20]])
    for line in health:
        print(line)

    state["last_run"] = {
        "at": now_iso(),
        "tracked_articles": len(articles),
        "article_updates_attempted": len(pending),
        "successful_notifications": successes,
        "failures": failures[-20:],
        "discovery_health": health,
    }
    save(state_path, state)

    write_summary([
        "### EdgeAI distribution",
        f"- Published Blogger articles tracked: **{len(articles)}**",
        f"- Article update batches attempted: **{len(pending)}**",
        f"- Successful service notifications: **{successes}**",
        f"- Failures this run: **{len(failures)}**",
        *[f"- {line}" for line in health],
    ])

    if failures and successes == 0 and (pending or feed_needed):
        print("ERROR: every distribution endpoint attempted in this run failed.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
