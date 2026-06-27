#!/usr/bin/env python3
"""
Deterministic viral-topic discovery for migukstory.com.

Measures what the news cycle is bursting on RIGHT NOW so the daily ingest
drafts high-demand topics first, instead of waiting for Steve to point at
them manually.

How it works (no Claude/API calls — pure RSS counting):
  1. Fetch broad "pulse" feeds (Google News sections) plus the regular
     drafting feeds from scripts/config/rss_sources.yml.
  2. Match every headline+summary against the topic clusters defined in
     scripts/config/viral_topics.yml.
  3. Score each cluster:
       breadth   = distinct feeds mentioning it today        (x3)
       burst     = today's hits vs 7-day rolling baseline    (x2, capped at 5)
       hits      = raw mention count                         (x1)
       relevance = static Korean-American weight from config (x1, 0-4)
       korean    = +2 if matched headlines mention Korea(n)/Koreatown
  4. Persist today's counts to scripts/state/viral_topics_history.json
     (rolling 14 days) so tomorrow's burst baseline is meaningful.
  5. Write the top clusters' keyword regexes to
     scripts/state/viral_boost_terms.json. draft_from_rss.py loads that
     file (if fresh) and gives matching feed items urgent-level selection
     priority. Editor grading still gates quality — a viral boost can only
     reorder candidates, never skip review.

Usage:
  python scripts/discover_viral_topics.py [--top N] [--threshold S]
                                          [--no-state] [--timeout S]

Options:
  --top N        Max clusters written to the boost file (default: 4).
  --threshold S  Minimum score for a cluster to qualify (default: 8.0).
  --no-state     Do not update history/boost files (dry inspection run).
  --timeout S    Per-feed fetch timeout via socket default (default: 15).
"""

from __future__ import annotations

import argparse
import json
import re
import socket
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
VIRAL_CONFIG = REPO / "scripts" / "config" / "viral_topics.yml"
RSS_CONFIG = REPO / "scripts" / "config" / "rss_sources.yml"
HISTORY = REPO / "scripts" / "state" / "viral_topics_history.json"
BOOST = REPO / "scripts" / "state" / "viral_boost_terms.json"

HISTORY_DAYS = 14
BASELINE_DAYS = 7

BREADTH_WEIGHT = 3.0
BURST_WEIGHT = 2.0
BURST_CAP = 5.0
KOREAN_BONUS = 2.0

# Severity tiers. A "breaking" cluster is one the whole news cycle is leading
# with right now (e.g. an Iran/Israel strike) — it is everywhere AND spiking
# vs its own baseline. These are the only topics allowed to claim the site's
# headline/featured slot. "hot" clusters still get drafting priority but do not
# auto-claim the headline. editor_grade.py reads this tier to decide whether a
# matching, quality-passing draft becomes the lead story.
BREAKING_MIN_BREADTH = 5     # mentioned across 5+ distinct feeds today
BREAKING_MIN_BURST = 2.0     # at least 2x its 7-day baseline
BREAKING_MIN_SCORE = 18.0    # or simply scoring very high overall


def classify_tier(breadth: int, burst: float, score: float) -> str:
    """breaking | hot — assumes the cluster already cleared the viral gate."""
    if (breadth >= BREAKING_MIN_BREADTH and burst >= BREAKING_MIN_BURST) \
            or score >= BREAKING_MIN_SCORE:
        return "breaking"
    return "hot"


def load_yaml(path: Path) -> dict:
    try:
        import yaml
    except ImportError:
        sys.exit("❌ PyYAML missing. Run: pip install -r scripts/requirements-draft.txt")
    if not path.exists():
        sys.exit(f"❌ Config not found: {path.relative_to(REPO)}")
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


_HTML_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")


def strip_html(s: str) -> str:
    s = _HTML_TAG.sub(" ", s)
    s = (s.replace("&nbsp;", " ").replace("&amp;", "&")
           .replace("&lt;", "<").replace("&gt;", ">")
           .replace("&quot;", '"').replace("&#39;", "'"))
    return _WS.sub(" ", s).strip()


def fetch_headlines(name: str, url: str) -> list[str]:
    """Return 'title — summary' strings for one feed; empty list on failure."""
    try:
        import feedparser
    except ImportError:
        sys.exit("❌ feedparser missing. Run: pip install -r scripts/requirements-draft.txt")
    parsed = feedparser.parse(url, request_headers={
        "User-Agent": "migukstory-viral-bot/1.0 (+https://migukstory.com)",
    })
    if getattr(parsed, "bozo", False) and not parsed.entries:
        print(f"⚠️  {name}: feed error ({getattr(parsed, 'bozo_exception', 'unknown')})",
              file=sys.stderr)
        return []
    out = []
    for entry in parsed.entries[:50]:
        title = strip_html(entry.get("title") or "")
        summary = strip_html(entry.get("summary") or entry.get("description") or "")[:300]
        if title:
            out.append(f"{title} — {summary}")
    return out


def load_history() -> dict:
    if not HISTORY.exists():
        return {"version": 1, "days": {}}
    try:
        data = json.loads(HISTORY.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        print(f"⚠️  corrupt {HISTORY.relative_to(REPO)} — starting fresh", file=sys.stderr)
        return {"version": 1, "days": {}}
    data.setdefault("days", {})
    return data


def baseline_for(history: dict, cluster: str, today: str) -> float:
    """Mean daily hits for `cluster` over up to BASELINE_DAYS prior days."""
    days = history.get("days", {})
    counts = [
        day_counts.get(cluster, 0)
        for date, day_counts in days.items()
        if date != today
    ]
    counts = counts[-BASELINE_DAYS:]
    if not counts:
        return 0.0
    return sum(counts) / len(counts)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--top", type=int, default=4)
    ap.add_argument("--threshold", type=float, default=8.0)
    ap.add_argument("--no-state", action="store_true")
    ap.add_argument("--timeout", type=int, default=15)
    args = ap.parse_args()

    socket.setdefaulttimeout(args.timeout)

    config = load_yaml(VIRAL_CONFIG)
    clusters = config.get("clusters") or []
    pulse_feeds = config.get("pulse_feeds") or []
    korean_terms = config.get("korean_angle_terms") or []
    if not clusters:
        sys.exit("❌ No clusters defined in viral_topics.yml")

    cluster_res: dict[str, re.Pattern] = {}
    cluster_meta: dict[str, dict] = {}
    for c in clusters:
        name = c["name"]
        cluster_res[name] = re.compile("|".join(c["keywords"]), re.IGNORECASE)
        cluster_meta[name] = c
    korean_re = re.compile("|".join(korean_terms), re.IGNORECASE) if korean_terms else None

    # Pulse feeds + the regular drafting feeds (for cross-source overlap).
    feeds: list[tuple[str, str]] = [(f["name"], f["url"]) for f in pulse_feeds]
    rss_cfg = load_yaml(RSS_CONFIG)
    for s in rss_cfg.get("sources") or []:
        if s.get("enabled", True):
            feeds.append((s["name"], s["url"]))

    hits: dict[str, int] = {name: 0 for name in cluster_res}
    feed_breadth: dict[str, set[str]] = {name: set() for name in cluster_res}
    korean_flag: dict[str, bool] = {name: False for name in cluster_res}
    sample_headlines: dict[str, list[str]] = {name: [] for name in cluster_res}

    fetched_ok = 0
    for feed_name, url in feeds:
        headlines = fetch_headlines(feed_name, url)
        if headlines:
            fetched_ok += 1
        for h in headlines:
            for cname, cre in cluster_res.items():
                if cre.search(h):
                    hits[cname] += 1
                    feed_breadth[cname].add(feed_name)
                    if korean_re and korean_re.search(h):
                        korean_flag[cname] = True
                    if len(sample_headlines[cname]) < 3:
                        sample_headlines[cname].append(h[:140])

    if fetched_ok == 0:
        sys.exit("❌ Every feed failed — refusing to write a boost file from no data.")

    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")
    history = load_history()

    scored: list[dict] = []
    for cname in cluster_res:
        base = baseline_for(history, cname, today)
        burst = hits[cname] / max(base, 0.5)
        breadth = len(feed_breadth[cname])
        score = (
            breadth * BREADTH_WEIGHT
            + min(burst, BURST_CAP) * BURST_WEIGHT
            + hits[cname]
            + float(cluster_meta[cname].get("relevance", 0))
            + (KOREAN_BONUS if korean_flag[cname] else 0.0)
        )
        scored.append({
            "name": cname,
            "category": cluster_meta[cname].get("category", ""),
            "hits": hits[cname],
            "breadth": breadth,
            "baseline": round(base, 2),
            "burst_ratio": round(burst, 2),
            "korean_angle": korean_flag[cname],
            "score": round(score, 2),
            "tier": classify_tier(breadth, burst, score),
            "samples": sample_headlines[cname],
        })
    scored.sort(key=lambda r: r["score"], reverse=True)

    # A cluster must be visible in 2+ feeds — one noisy feed is not "viral".
    viral = [r for r in scored if r["score"] >= args.threshold and r["breadth"] >= 2]
    viral = viral[: max(1, args.top)]

    print(f"\n🔥 바이럴 토픽 리포트 ({today}, 피드 {fetched_ok}/{len(feeds)}개 수집)")
    for r in scored:
        marker = "🚨" if (r in viral and r["tier"] == "breaking") else "🔥" if r in viral else "  "
        print(f" {marker} {r['name']:<28} score={r['score']:>6}  "
              f"hits={r['hits']:>3} feeds={r['breadth']:>2} "
              f"burst=x{r['burst_ratio']:<5} tier={r['tier']:<8} "
              f"{'🇰🇷' if r['korean_angle'] else ''}")
    if viral:
        print("\n   오늘 드래프트에서 우선순위를 받는 클러스터:")
        for r in viral:
            tier_ko = "🚨속보(헤드라인 후보)" if r["tier"] == "breaking" else "🔥핫토픽"
            print(f"   - [{tier_ko}] {r['name']} ({r['category']}) — 예시: {r['samples'][0] if r['samples'] else 'n/a'}")
    else:
        print("\n   임계값을 넘는 바이럴 토픽 없음 — 부스트 파일은 비워둡니다.")

    if args.no_state:
        print("\n🧪 --no-state: history/boost 파일을 쓰지 않습니다.")
        return 0

    # Persist rolling history (last HISTORY_DAYS days).
    history["days"][today] = {name: hits[name] for name in cluster_res}
    cutoff = (now - timedelta(days=HISTORY_DAYS)).strftime("%Y-%m-%d")
    history["days"] = {d: c for d, c in sorted(history["days"].items()) if d >= cutoff}
    HISTORY.parent.mkdir(parents=True, exist_ok=True)
    HISTORY.write_text(json.dumps(history, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    boost = {
        "generated_at": now.isoformat(timespec="seconds"),
        "clusters": [
            {
                "name": r["name"],
                "category": r["category"],
                "score": r["score"],
                # tier drives editor headline decisions; "breaking" clusters are
                # the only ones allowed to claim the site's featured/lead slot.
                "tier": r["tier"],
                "breadth": r["breadth"],
                "burst_ratio": r["burst_ratio"],
                "korean_angle": r["korean_angle"],
                # one sample headline so the editor (and humans reading the
                # report) can see WHAT the cluster is about today.
                "sample": r["samples"][0] if r["samples"] else "",
                "terms": cluster_meta[r["name"]]["keywords"],
            }
            for r in viral
        ],
    }
    BOOST.write_text(json.dumps(boost, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"\n✅ {BOOST.relative_to(REPO)} 갱신 ({len(viral)}개 클러스터)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
