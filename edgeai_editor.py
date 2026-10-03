#!/usr/bin/env python3
"""Central EdgeAI editor/publisher.

This is the only scheduled runner allowed to call Gemini or write Blogger posts.
Discovery runners only feed queue_fast.json and queue_deep.json.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import edgeai as core

ROOT = Path(__file__).resolve().parent
QUEUE_PATHS = (ROOT / "queue_fast.json", ROOT / "queue_deep.json")
STATE_PATH = ROOT / "editor_state.json"
CONFIG_PATH = ROOT / "bootstrap_config.json"
NORMAL_FRESH_HOURS = 72


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


def publish_candidate(item: dict, state: dict, key: str, blog_id: str, access: str):
    decision = core.ask_editor(item, key)
    score = int(decision.get("score", 0))
    should_publish = bool(decision.get("publish")) and score >= 75
    status = str(decision.get("status", "DEVELOPING")).upper()
    if status not in {"CONFIRMED", "DEVELOPING", "EARLY SIGNAL", "RUMOUR"}:
        status = "DEVELOPING"
    skey = core.story_key(str(decision.get("story_key", "")), str(decision.get("title") or item["title"]))

    if not should_publish:
        return "ignored", score, skey, str(decision.get("reason", ""))[:500], False

    existing_story = state.setdefault("stories", {}).get(skey)
    existing_post = None
    if existing_story and existing_story.get("post_id"):
        existing_post = core.blogger("GET", f"blogs/{blog_id}/posts/{existing_story['post_id']}", access)
        decision = core.ask_editor(item, key, existing_post)
        score = int(decision.get("score", score))
        if not bool(decision.get("publish", True)) or score < 75:
            return "ignored_update", score, skey, str(decision.get("reason", ""))[:500], False
        status = str(decision.get("status", status)).upper()
        if status not in {"CONFIRMED", "DEVELOPING", "EARLY SIGNAL", "RUMOUR"}:
            status = "DEVELOPING"

    title = str(decision.get("title") or item["title"]).strip()[:160]
    body = str(decision.get("body_html", "")).strip()
    if len(core.clean_text(body)) < 180:
        raise RuntimeError("Generated body too short; refusing to publish")
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
        "source_urls": source_urls,
        "last_updated": core.now_iso(),
    })
    return action, score, skey, post.get("url", ""), is_new


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
    blog_id = core.env("BLOGGER_BLOG_ID")
    access = core.token()
    core.blog_check(access, blog_id)

    evaluated = published_actions = new_posts = 0
    for item in pool[:eval_cap]:
        if published_actions >= publish_cap:
            break
        candidate_id = item["candidate_id"]
        try:
            action, score, skey, detail, is_new = publish_candidate(item, state, key, blog_id, access)
            evaluated += 1
            state["processed"][candidate_id] = {
                "url": item.get("url", ""), "status": action, "score": score,
                "story_key": skey, "at": core.now_iso(), "bootstrap": bool(item.get("bootstrap")),
            }
            if action in {"published", "updated"}:
                published_actions += 1
                if is_new:
                    new_posts += 1
                    if active:
                        state["bootstrap"]["published"] = int(state["bootstrap"].get("published", 0)) + 1
                print(f"{action.upper()} {score}: {detail}")
            else:
                print(f"IGNORED {score}: {item.get('title', '')}")
        except Exception as exc:
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

    if active and not state["bootstrap"].get("complete"):
        remaining_bootstrap = [i for i in eligible(items, state, True)]
        if not remaining_bootstrap:
            state["bootstrap"]["complete"] = True
            state["bootstrap"]["completed_at"] = core.now_iso()

    state["last_run"] = {
        "at": core.now_iso(), "mode": "bootstrap" if active else "live",
        "eligible": len(pool), "evaluated": evaluated,
        "publish_actions": published_actions, "new_posts": new_posts,
    }
    save(STATE_PATH, state)
    boot = state.get("bootstrap", {})
    print(
        f"EDITOR COMPLETE: mode={'bootstrap' if active else 'live'}; evaluated={evaluated}; "
        f"publish_actions={published_actions}; bootstrap_posts={boot.get('published', 0)}/{boot.get('target', 30)}; "
        f"bootstrap_complete={boot.get('complete', False)}."
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("check", "auto", "bootstrap", "live"), default="check")
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
