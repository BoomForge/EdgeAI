#!/usr/bin/env python3
"""EdgeAI v2 runner: RSS/Atom + HTML discovery + page-delta signals."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

import edgeai as core

ROOT = Path(__file__).resolve().parent
WEB_SOURCES_PATH = ROOT / "web_sources.json"
ORIGINAL_FETCH_FEED = core.fetch_feed

DATE_PATTERNS = (
    r"\b(20\d{2}-\d{2}-\d{2})\b",
    r"\b((?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{1,2},\s+20\d{2})\b",
)


def _request(url: str) -> tuple[str, str]:
    response = requests.get(
        url,
        timeout=core.TIMEOUT,
        headers={
            "User-Agent": core.USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )
    response.raise_for_status()
    return response.url, response.text


def _clean_page(html_text: str) -> BeautifulSoup:
    soup = BeautifulSoup(html_text, "html.parser")
    for node in soup(["script", "style", "svg", "noscript", "form", "iframe"]):
        node.decompose()
    return soup


def _date_from(text: str) -> str:
    for pattern in DATE_PATTERNS:
        match = re.search(pattern, text, re.I)
        if match:
            return match.group(1)
    return ""


def _candidate(title: str, url: str, summary: str, source: dict, published: str = "") -> dict:
    return {
        "title": re.sub(r"\s+", " ", title).strip()[:240],
        "url": url.split("#edgeai-", 1)[0] if "#edgeai-" not in url else url,
        "published": published,
        "summary": re.sub(r"\s+", " ", summary).strip()[:5000],
        "source_name": source["name"],
        "priority": int(source.get("priority", 2)),
        "kind": source.get("kind", "web"),
    }


def _unique(items: list[dict], limit: int) -> list[dict]:
    seen = set()
    out = []
    for item in items:
        key = item["url"]
        if key in seen or not item.get("title"):
            continue
        seen.add(key)
        out.append(item)
        if len(out) >= limit:
            break
    return out


def fetch_futuretools(source: dict) -> list[dict]:
    final_url, raw = _request(source["url"])
    soup = _clean_page(raw)
    host = urlparse(final_url).netloc.lower().removeprefix("www.")
    ignored = {"youtube.com", "x.com", "twitter.com", "instagram.com", "facebook.com"}
    items = []
    for anchor in soup.select("a[href]"):
        href = urljoin(final_url, anchor.get("href", "").strip())
        parsed = urlparse(href)
        link_host = parsed.netloc.lower().removeprefix("www.")
        text = core.clean_text(anchor.get_text(" ", strip=True))
        if not parsed.scheme.startswith("http") or not link_host or link_host == host:
            continue
        if link_host in ignored or any(link_host.endswith("." + d) for d in ignored):
            continue
        if len(text) < 22:
            continue
        parent_text = core.clean_text(anchor.parent.get_text(" ", strip=True) if anchor.parent else text)
        items.append(_candidate(text, href, parent_text, source, _date_from(parent_text)))
    return _unique(items, int(source.get("max_items", 12)))


def fetch_links(source: dict) -> list[dict]:
    final_url, raw = _request(source["url"])
    soup = _clean_page(raw)
    base_host = urlparse(final_url).netloc.lower().removeprefix("www.")
    regex = re.compile(source.get("href_regex", ".*"), re.I)
    same_domain = bool(source.get("same_domain", False))
    min_text = int(source.get("min_text", 7))
    items = []

    for anchor in soup.select("a[href]"):
        raw_href = anchor.get("href", "").strip()
        if not raw_href or raw_href.startswith(("#", "mailto:", "javascript:")):
            continue
        href = urljoin(final_url, raw_href)
        parsed = urlparse(href)
        link_host = parsed.netloc.lower().removeprefix("www.")
        if not parsed.scheme.startswith("http"):
            continue
        if same_domain and link_host != base_host:
            continue
        if not regex.search(href):
            continue
        if href.rstrip("/") == final_url.rstrip("/"):
            continue
        text = core.clean_text(anchor.get_text(" ", strip=True))
        parent_text = core.clean_text(anchor.parent.get_text(" ", strip=True) if anchor.parent else text)
        title = text if len(text) >= min_text else parent_text
        if len(title) < min_text:
            continue
        bad = title.lower().strip()
        if bad in {"read more", "learn more", "news", "blog", "research", "home", "about", "contact"}:
            continue
        items.append(_candidate(title, href, parent_text, source, _date_from(parent_text)))

    return _unique(items, int(source.get("max_items", 10)))


def fetch_snapshot(source: dict) -> list[dict]:
    final_url, raw = _request(source["url"])
    soup = _clean_page(raw)
    main = soup.find("main") or soup.find("article") or soup.body or soup
    text = core.clean_text(main.get_text(" ", strip=True))
    text = re.sub(r"\s+", " ", text).strip()
    max_chars = int(source.get("max_chars", 8000))
    text = text[:max_chars]
    if len(text) < 80:
        raise RuntimeError("snapshot page produced too little readable text")
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:20]
    synthetic_url = f"{final_url.split('#', 1)[0]}#edgeai-{digest}"
    return [_candidate(source.get("title", f"{source['name']} changed"), synthetic_url, text, source, core.now_iso())]


def fetch_any(source: dict) -> list[dict]:
    adapter = source.get("adapter")
    if not adapter:
        return ORIGINAL_FETCH_FEED(source)
    if adapter == "futuretools":
        return fetch_futuretools(source)
    if adapter == "links":
        return fetch_links(source)
    if adapter == "snapshot":
        return fetch_snapshot(source)
    raise RuntimeError(f"unknown web adapter: {adapter}")


def load_sources() -> list[dict]:
    feed_sources = core.load_json(core.SOURCES_PATH, {"sources": []}).get("sources", [])
    web_sources = core.load_json(WEB_SOURCES_PATH, {"sources": []}).get("sources", [])
    return [*feed_sources, *web_sources]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("check", "baseline", "live"), default="check")
    args = parser.parse_args()
    sources = load_sources()
    if not sources:
        raise RuntimeError("No EdgeAI sources configured")
    core.fetch_feed = fetch_any
    {"check": core.mode_check, "baseline": core.mode_baseline, "live": core.mode_live}[args.mode](sources)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"FATAL: {exc}", file=__import__("sys").stderr)
        raise SystemExit(1)
