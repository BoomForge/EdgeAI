#!/usr/bin/env python3
"""EdgeAI discovery runner.

Discovery never calls Gemini and never publishes. Each lane owns its state and queue
file so new source runners can be added without sharing mutable state.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import edgeai as core
import edgeai_runner as adapters

ROOT = Path(__file__).resolve().parent
LANES = {
    "fast": {
        "sources": ROOT / "sources.json",
        "state": ROOT / "discovery_fast_state.json",
        "queue": ROOT / "queue_fast.json",
    },
    "deep": {
        "sources": ROOT / "web_sources.json",
        "state": ROOT / "discovery_deep_state.json",
        "queue": ROOT / "queue_deep.json",
    },
}
NORMAL_FRESH_HOURS = 72
BOOTSTRAP_LOOKBACK_HOURS = 24 * 14
QUEUE_MAX = 250


def load(path: Path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def save(path: Path, data) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def source_list(path: Path) -> list[dict]:
    return load(path, {"sources": []}).get("sources", [])


def candidate_id(url: str) -> str:
    # Page-delta adapters intentionally encode the content hash as #edgeai-....
    # Preserve that fragment so a changed benchmark/ranking page becomes a new signal.
    normalized = url if "#edgeai-" in url else url.split("#", 1)[0]
    return hashlib.sha256(normalized.encode()).hexdigest()[:24]


def item_time(item: dict):
    return core.parse_date(item.get("published", ""))


def queue_rank(item: dict):
    published = item_time(item) or datetime(1970, 1, 1, tzinfo=timezone.utc)
    return (
        0 if item.get("bootstrap") else 1,
        int(item.get("priority", 2)),
        -int(item.get("search_score", 0)),
        -published.timestamp(),
    )


def prune_queue(items: list[dict]) -> list[dict]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=BOOTSTRAP_LOOKBACK_HOURS)
    unique = {}
    for item in items:
        published = item_time(item)
        discovered = core.parse_date(item.get("discovered_at", ""))
        if published and published < cutoff and not item.get("bootstrap"):
            continue
        if not published and discovered and discovered < cutoff:
            continue
        unique[item["candidate_id"]] = item
    return sorted(unique.values(), key=queue_rank)[:QUEUE_MAX]


def check(lane: str) -> None:
    sources = source_list(LANES[lane]["sources"])
    ok = failed = 0
    for source in sources:
        if not source.get("enabled", True):
            continue
        try:
            items = adapters.fetch_any(source)
            print(f"Source: OK - {source['name']} ({len(items)} items)")
            ok += 1
        except Exception as exc:
            print(f"Source: WARN - {source['name']}: {exc}")
            failed += 1
    if not ok:
        raise RuntimeError(f"{lane}: no sources could be read")
    print(f"DISCOVERY CHECK PASSED: lane={lane}; {ok} sources OK; {failed} warnings. No AI and nothing published.")


def run(lane: str, baseline: bool = False) -> None:
    paths = LANES[lane]
    sources = source_list(paths["sources"])
    state = load(paths["state"], {"version": 2, "seen": {}, "runs": 0})
    queue = load(paths["queue"], {"version": 2, "lane": lane, "candidates": []})
    state.setdefault("seen", {})
    state["runs"] = int(state.get("runs", 0)) + 1

    # First real run intentionally rebuilds a launch pool from up to 14 days.
    # Later runs are a 72-hour rolling radar.
    first_discovery = not state["seen"] and not baseline
    lookback = BOOTSTRAP_LOOKBACK_HOURS if first_discovery else NORMAL_FRESH_HOURS
    cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback)
    candidates = [] if baseline else list(queue.get("candidates", []))
    added = ok = failed = filtered = old = 0

    for source in sources:
        if not source.get("enabled", True):
            continue
        try:
            items = adapters.fetch_any(source)
            ok += 1
        except Exception as exc:
            print(f"Source warning - {source['name']}: {exc}")
            failed += 1
            continue

        for item in items:
            item_id = candidate_id(item["url"])
            if item_id in state["seen"]:
                continue
            published = item_time(item)
            if published and published < cutoff:
                state["seen"][item_id] = {"url": item["url"], "status": "too_old", "first_seen": core.now_iso()}
                old += 1
                continue
            if not core.passes_prefilter(item):
                state["seen"][item_id] = {
                    "url": item["url"], "status": "prefiltered",
                    "search_score": int(item.get("search_score", 0)), "first_seen": core.now_iso(),
                }
                filtered += 1
                continue

            state["seen"][item_id] = {"url": item["url"], "status": "baseline" if baseline else "queued", "first_seen": core.now_iso()}
            if baseline:
                continue
            item["candidate_id"] = item_id
            item["lane"] = lane
            item["discovered_at"] = core.now_iso()
            item["bootstrap"] = bool(first_discovery)
            item["search_score"] = int(item.get("search_score", core.search_signal_score(item.get("title", ""), item.get("summary", ""))))
            candidates.append(item)
            added += 1

    if not baseline:
        queue["candidates"] = prune_queue(candidates)
        queue["updated_at"] = core.now_iso()
        save(paths["queue"], queue)

    state["last_run"] = {
        "at": core.now_iso(), "mode": "baseline" if baseline else "discover",
        "sources_ok": ok, "warnings": failed, "queued": added,
        "prefiltered": filtered, "too_old": old, "bootstrap_seed": first_discovery,
    }
    save(paths["state"], state)
    print(
        f"DISCOVERY COMPLETE: lane={lane}; queued={added}; prefiltered={filtered}; "
        f"too_old={old}; sources={ok}; warnings={failed}; bootstrap={first_discovery}. "
        "No AI and nothing published."
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lane", choices=tuple(LANES), required=True)
    parser.add_argument("--mode", choices=("check", "baseline", "discover"), default="check")
    args = parser.parse_args()
    if args.mode == "check":
        check(args.lane)
    else:
        run(args.lane, baseline=args.mode == "baseline")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"FATAL: {exc}", file=__import__("sys").stderr)
        raise SystemExit(1)
