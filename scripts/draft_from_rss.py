#!/usr/bin/env python3
"""
Daily-draft generator for migukstory.com.

Fetches configured RSS feeds, dedupes against scripts/state/seen_urls.json,
and asks Claude to produce a Korean-language draft post for human review.

Drafts are written to drafts/ only. This script never touches queue/ or
src/content/blog/ — promotion to queue/ requires human review.

Usage:
  python scripts/draft_from_rss.py [--dry-run] [--max-drafts N]

Options:
  --dry-run        Fetch + dedupe + plan, but do not call the Claude API,
                   write drafts, or update the dedupe store. Safe to run
                   without ANTHROPIC_API_KEY.
  --max-drafts N   Cap drafts produced this run (default: 5). Hard ceiling
                   is also 5 — values larger than that are clamped.

Env vars:
  ANTHROPIC_API_KEY   Required unless --dry-run. Read from environment;
                      never logged. In CI, supply via GitHub Secrets.
  ANTHROPIC_MODEL     Optional model override. Default: claude-sonnet-4-6.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode

REPO = Path(__file__).resolve().parent.parent
DRAFTS = REPO / "drafts"
QUEUE = REPO / "queue"
BLOG = REPO / "src" / "content" / "blog"
CONFIG = REPO / "scripts" / "config" / "rss_sources.yml"
STATE = REPO / "scripts" / "state" / "seen_urls.json"

HARD_CAP_DRAFTS = 5
DEFAULT_MAX_ITEMS_PER_FEED = 3
DEFAULT_MODEL = "claude-sonnet-4-6"

VALID_CATEGORIES = {
    "immigration", "tax", "health", "education",
    "retirement", "community", "real-estate", "economy",
}

# Stripped from query strings during URL canonicalization.
TRACKING_PARAM_PREFIXES = ("utm_", "fbclid", "gclid", "mc_cid", "mc_eid",
                            "ref", "ref_", "_hsenc", "_hsmi")


@dataclass
class FeedItem:
    source_name: str
    category: str
    title: str
    url: str
    canonical_url: str
    summary: str
    published: str  # ISO date or empty


# --------------------------------------------------------------------------
# Config / state I/O
# --------------------------------------------------------------------------

def load_sources() -> list[dict]:
    try:
        import yaml
    except ImportError:
        sys.exit("❌ PyYAML missing. Run: pip install -r scripts/requirements-draft.txt")
    if not CONFIG.exists():
        sys.exit(f"❌ Config not found: {CONFIG.relative_to(REPO)}")
    data = yaml.safe_load(CONFIG.read_text(encoding="utf-8")) or {}
    sources = data.get("sources") or []
    out = []
    for s in sources:
        if not s.get("enabled", True):
            continue
        cat = s.get("category")
        if cat not in VALID_CATEGORIES:
            print(f"⚠️  Skipping {s.get('name')!r}: invalid category {cat!r}", file=sys.stderr)
            continue
        out.append(s)
    return out


def load_seen() -> dict[str, Any]:
    if not STATE.exists():
        return {"version": 1, "seen": {}}
    try:
        data = json.loads(STATE.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        sys.exit(f"❌ Corrupt dedupe store {STATE.relative_to(REPO)}: {e}")
    data.setdefault("seen", {})
    return data


def save_seen(data: dict[str, Any]) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    # Stable ordering keeps diffs readable in PRs.
    seen = data.get("seen", {})
    data["seen"] = dict(sorted(seen.items()))
    STATE.write_text(
        json.dumps(data, indent=2, ensure_ascii=False, sort_keys=False) + "\n",
        encoding="utf-8",
    )


# --------------------------------------------------------------------------
# URL canonicalization
# --------------------------------------------------------------------------

def canonical_url(url: str) -> str:
    """Normalize a URL so trivial variants dedupe against each other."""
    try:
        p = urlparse(url.strip())
    except ValueError:
        return url.strip()
    if not p.scheme or not p.netloc:
        return url.strip()
    scheme = "https" if p.scheme in ("http", "https") else p.scheme
    netloc = p.netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    # Drop tracking params, keep meaningful ones.
    kept = [
        (k, v) for (k, v) in parse_qsl(p.query, keep_blank_values=False)
        if not any(k.lower().startswith(prefix) for prefix in TRACKING_PARAM_PREFIXES)
    ]
    query = urlencode(sorted(kept))
    path = p.path.rstrip("/") or "/"
    return urlunparse((scheme, netloc, path, "", query, ""))


# --------------------------------------------------------------------------
# Feed fetch
# --------------------------------------------------------------------------

def fetch_feed(source: dict) -> list[FeedItem]:
    try:
        import feedparser
    except ImportError:
        sys.exit("❌ feedparser missing. Run: pip install -r scripts/requirements-draft.txt")

    url = source["url"]
    name = source["name"]
    category = source["category"]
    max_items = int(source.get("max_items") or DEFAULT_MAX_ITEMS_PER_FEED)

    parsed = feedparser.parse(url, request_headers={
        "User-Agent": "migukstory-draft-bot/1.0 (+https://migukstory.com)",
    })
    if getattr(parsed, "bozo", False) and not parsed.entries:
        print(f"⚠️  {name}: feed error ({getattr(parsed, 'bozo_exception', 'unknown')})",
              file=sys.stderr)
        return []

    items: list[FeedItem] = []
    for entry in parsed.entries[:max_items]:
        link = (entry.get("link") or "").strip()
        title = (entry.get("title") or "").strip()
        if not link or not title:
            continue
        summary = strip_html(entry.get("summary") or entry.get("description") or "")
        published = entry.get("published") or entry.get("updated") or ""
        items.append(FeedItem(
            source_name=name,
            category=category,
            title=title,
            url=link,
            canonical_url=canonical_url(link),
            summary=summary[:1200],
            published=published,
        ))
    return items


_HTML_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")

def strip_html(s: str) -> str:
    s = _HTML_TAG.sub(" ", s)
    s = (s.replace("&nbsp;", " ").replace("&amp;", "&")
           .replace("&lt;", "<").replace("&gt;", ">")
           .replace("&quot;", '"').replace("&#39;", "'"))
    return _WS.sub(" ", s).strip()


# --------------------------------------------------------------------------
# Slug + frontmatter
# --------------------------------------------------------------------------

def slugify(title: str, fallback: str) -> str:
    s = title.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    if len(s) < 6:  # mostly non-ASCII title — fall back to URL stem.
        s = fallback
        s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    if not s:
        s = "draft"
    return s[:80].rstrip("-")


def unique_path(directory: Path, slug: str) -> Path:
    """Find a non-colliding <slug>.md inside `directory`. Suffix with -2, -3…"""
    candidate = directory / f"{slug}.md"
    i = 2
    while candidate.exists():
        candidate = directory / f"{slug}-{i}.md"
        i += 1
    return candidate


# --------------------------------------------------------------------------
# Claude call
# --------------------------------------------------------------------------

PROMPT_SYSTEM = """You write Korean-language news briefs for migukstory.com,
a site for the Korean-American immigrant community. Voice is that of a
trusted community newspaper: factual, plain, second-person 존댓말, no
fluff. You write ONLY from the source material provided.

Hard rules (non-negotiable):
- Output is Markdown ONLY (no code fences around the whole thing, no
  preamble, no postscript).
- Output starts with YAML frontmatter delimited by --- lines, then body.
- Direct quotes from the source must each be 25 Korean characters or
  fewer (or ~15 English words). Paraphrase the rest. Never copy whole
  sentences verbatim.
- Every factual claim must be traceable to the source provided. Do NOT
  introduce numbers, names, or events not present in the source.
- Always include a final "## 출처 (Sources)" section with the source name
  and the canonical URL given to you. Do not invent additional sources.
- Never give legal, tax, or medical advice. Where the topic touches
  these, add: "전문가 상담을 권장합니다."
- Korean throughout. Use English only for proper names, acronyms, or
  direct quotes."""


PROMPT_USER_TEMPLATE = """다음 영어 원문 기사 한 건을 바탕으로 migukstory.com용 한국어
초안을 작성하세요. 사람 검토 전 단계이므로 출처 표기를 반드시 포함하세요.

원문 정보:
- 출처(source): {source_name}
- 카테고리(category): {category}
- 원문 제목: {title}
- 원문 링크(canonical): {canonical_url}
- 발행일(원문): {published}
- 요약/본문 발췌:
\"\"\"
{summary}
\"\"\"

다음 형식으로 출력하세요. 코드펜스 없이 마크다운만:

---
title: '한국어 제목 (60자 이내, 따옴표는 두 개로 이스케이프)'
description: '메타 설명 120~155자'
pubDate: '{today}'
tags: ['태그1', '태그2', '태그3']
category: '{category}'
ageGroup: 'all'
draft: true
source: '{source_name}'
sourceUrl: '{canonical_url}'
---

# 한국어 제목

[3~5문단의 한국어 본문. 한 문단당 2~4문장. 직접 인용은 25자 이내.
숫자/날짜/이름은 원문에 있는 것만 사용. 한인 독자 관점에서 왜 중요한지
한 문단 정도 분석을 더해도 좋음. 단, 원문에 없는 새로운 사실은 금지.]

## 핵심 요약

- [핵심 포인트 1]
- [핵심 포인트 2]
- [핵심 포인트 3]

## 출처 (Sources)

- [{source_name}]({canonical_url})
"""


def call_claude(item: FeedItem, model: str) -> str:
    try:
        from anthropic import Anthropic
    except ImportError:
        sys.exit("❌ anthropic SDK missing. Run: pip install -r scripts/requirements-draft.txt")

    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        sys.exit("❌ ANTHROPIC_API_KEY is not set. "
                 "Set it in your shell or GitHub Secrets. "
                 "For local testing without a key, pass --dry-run.")

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    user_prompt = PROMPT_USER_TEMPLATE.format(
        source_name=item.source_name,
        category=item.category,
        title=item.title,
        canonical_url=item.canonical_url,
        published=item.published or "(원문 미명시)",
        summary=item.summary or "(요약 없음 — 제목과 링크만 사용)",
        today=today,
    )

    client = Anthropic(api_key=api_key)
    msg = client.messages.create(
        model=model,
        max_tokens=2400,
        system=PROMPT_SYSTEM,
        messages=[{"role": "user", "content": user_prompt}],
    )
    parts = [b.text for b in msg.content if getattr(b, "type", None) == "text"]
    return "".join(parts).strip()


# --------------------------------------------------------------------------
# Safety checks on generated draft
# --------------------------------------------------------------------------

def looks_like_valid_draft(md: str, item: FeedItem) -> tuple[bool, str]:
    if not md.startswith("---"):
        return False, "missing leading frontmatter"
    # Two frontmatter delimiters before the body.
    if md.count("\n---\n") < 1 and md.count("\n---") < 2:
        return False, "frontmatter not closed"
    if item.canonical_url not in md:
        return False, "canonical source URL not included"
    if "## 출처" not in md and "출처 (Sources)" not in md:
        return False, "missing 출처 section"
    return True, ""


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--dry-run", action="store_true",
                   help="Plan only — no API calls, no writes.")
    p.add_argument("--max-drafts", type=int, default=HARD_CAP_DRAFTS,
                   help=f"Cap drafts this run (1..{HARD_CAP_DRAFTS}). Default: {HARD_CAP_DRAFTS}.")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    max_drafts = max(1, min(args.max_drafts, HARD_CAP_DRAFTS))
    model = os.environ.get("ANTHROPIC_MODEL", DEFAULT_MODEL)

    # Guardrail: this script must never write to queue/ or blog/.
    # Anything touching those paths is a bug.
    assert QUEUE not in DRAFTS.parents and BLOG not in DRAFTS.parents

    sources = load_sources()
    if not sources:
        print("⚠️  No enabled sources in config. Nothing to do.")
        return 0

    state = load_seen()
    seen: dict[str, Any] = state.get("seen", {})

    # Gather + dedupe candidate items.
    candidates: list[FeedItem] = []
    for src in sources:
        print(f"📰 {src['name']}: fetching {src['url']}")
        for item in fetch_feed(src):
            if item.canonical_url in seen:
                continue
            # Also skip if a draft for this URL is already on disk.
            if any(item.canonical_url in p.read_text(encoding="utf-8", errors="ignore")
                   for p in DRAFTS.glob("*.md")):
                continue
            candidates.append(item)

    if not candidates:
        print("✅ Nothing new — all feed items already seen.")
        return 0

    # Round-robin across sources so one feed can't monopolize the quota.
    by_source: dict[str, list[FeedItem]] = {}
    for c in candidates:
        by_source.setdefault(c.source_name, []).append(c)
    selected: list[FeedItem] = []
    while len(selected) < max_drafts and any(by_source.values()):
        for name in list(by_source):
            if not by_source[name]:
                continue
            selected.append(by_source[name].pop(0))
            if len(selected) >= max_drafts:
                break

    print(f"\n🎯 Planning {len(selected)} draft(s) "
          f"(max {max_drafts}, hard cap {HARD_CAP_DRAFTS}):")
    for it in selected:
        print(f"   - [{it.category}] {it.source_name}: {it.title[:80]}")

    if args.dry_run:
        print("\n🧪 --dry-run: skipping Claude calls and file writes.")
        return 0

    DRAFTS.mkdir(parents=True, exist_ok=True)

    written: list[Path] = []
    failures: list[tuple[FeedItem, str]] = []
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    for item in selected:
        print(f"\n🤖 Generating: {item.title[:80]}")
        try:
            md = call_claude(item, model=model)
        except SystemExit:
            raise
        except Exception as e:
            print(f"   ❌ Claude call failed: {e}", file=sys.stderr)
            failures.append((item, f"claude error: {e}"))
            continue

        ok, reason = looks_like_valid_draft(md, item)
        if not ok:
            print(f"   ❌ Draft rejected: {reason}", file=sys.stderr)
            failures.append((item, reason))
            continue

        url_stem = Path(urlparse(item.url).path).stem or "draft"
        slug = f"{today}-{slugify(item.title, fallback=url_stem)}"
        out = unique_path(DRAFTS, slug)
        # Final guardrail before write.
        if out.is_relative_to(QUEUE) or out.is_relative_to(BLOG):
            sys.exit(f"❌ refusing to write outside drafts/: {out}")
        out.write_text(md.rstrip() + "\n", encoding="utf-8")
        print(f"   ✅ Wrote {out.relative_to(REPO)}")
        written.append(out)

        seen[item.canonical_url] = {
            "first_seen": today,
            "source": item.source_name,
            "title": item.title,
            "draft": str(out.relative_to(REPO)),
        }

    # Persist dedupe updates only for items we actually drafted.
    if written:
        save_seen(state)
        print(f"\n💾 Updated dedupe store: {STATE.relative_to(REPO)}")

    print(f"\n📊 Wrote {len(written)} draft(s); {len(failures)} failure(s).")
    for it, why in failures:
        print(f"   ! {it.source_name} :: {it.title[:60]} — {why}")

    return 0 if written or not failures else 1


if __name__ == "__main__":
    sys.exit(main())
