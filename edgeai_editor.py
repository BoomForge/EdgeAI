#!/usr/bin/env python3
"""Central EdgeAI editor/publisher.

This is the only scheduled runner allowed to call Gemini or write Blogger posts.
Discovery runners only feed queue_fast.json and queue_deep.json.
"""
from __future__ import annotations

import argparse
import html
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

    status_adjust = {
        "CONFIRMED": 6,
        "DEVELOPING": -2,
        "EARLY SIGNAL": -12,
        "RUMOUR": -28,
    }
    score += status_adjust.get(status, -8)

    if len(summary) >= 200:
        score += 3
    elif len(summary) >= 80:
        score += 1
    else:
        score -= 4

    if item.get("published"):
        score += 2
    else:
        score -= 2

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
        color = "#70f0b1"
    elif score >= 75:
        color = "#8ee6c4"
    elif score >= 60:
        color = "#ffc96b"
    elif score >= 40:
        color = "#ff9f5a"
    else:
        color = "#ff557f"

    safe_label = html.escape(label)
    safe_reason = html.escape(reason)
    safe_source = html.escape(source_name)
    return f"""
<div class="edge-trust-card" style="display:flex;align-items:center;gap:14px;margin:0 0 22px;padding:14px 16px;border:1px solid #223247;border-radius:14px;background:#0d141d;color:#eef8ff;">
  <div role="img" aria-label="Evidence Trust {score} out of 100" title="Evidence Trust {score}/100" style="width:62px;height:62px;min-width:62px;border-radius:50%;padding:5px;background:conic-gradient({color} 0 {score}%,#223247 {score}% 100%);">
    <div style="width:52px;height:52px;border-radius:50%;background:#070b11;display:flex;align-items:center;justify-content:center;font:800 17px Arial,sans-serif;color:{color};">{score}</div>
  </div>
  <div style="min-width:0;">
    <div style="font:800 11px Arial,sans-serif;letter-spacing:1px;text-transform:uppercase;color:#91a6ba;">Evidence Trust · {safe_source}</div>
    <div style="font:800 17px Arial,sans-serif;color:{color};margin:2px 0 3px;">{safe_label}</div>
    <div style="font:13px/1.45 Arial,sans-serif;color:#c7d5e0;">{safe_reason}</div>
    <div style="font:11px/1.4 Arial,sans-serif;color:#91a6ba;margin-top:5px;">Evidence confidence for this report, not a permanent rating of the company or site.</div>
  </div>
</div>
""".strip()


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
    body = trust_card(trust_score, trust_name, trust_reason, str(item.get("source_name", "Source"))) + body

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
        "source_urls": source_urls,
        "last_updated": core.now_iso(),
    })
    return action, score, skey, post.get("url", ""), is_new, trust


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
