#!/usr/bin/env python3
"""
Daily-draft generator for migukstory.com.

Fetches configured RSS feeds, dedupes against scripts/state/seen_urls.json,
and asks Claude to produce a Korean-language draft post for human review.

Drafts are written to drafts/ only. This script never touches queue/ or
src/content/blog/ — promotion to queue/ requires human review.

Usage:
  python scripts/draft_from_rss.py [--dry-run] [--max-drafts N]
                                   [--manifest PATH] [--time-budget S]
                                   [--cli-timeout S]
                                   [--urgent-only] [--tier1-only]

Options:
  --dry-run        Fetch + dedupe + plan, but do not call the Claude API,
                   write drafts, or update the dedupe store. Safe to run
                   without ANTHROPIC_API_KEY.
  --max-drafts N   Global cap for drafts produced this run (default: 24).
  --max-per-category N
                   Target cap per category (default: 3), so the editor sees
                   enough candidates across immigration/tax/health/etc.
                   Items matching URGENT_TERMS (USCIS / I-485 / IRS guidance
                   / FDA recall / CPI / interest rate / etc.) are picked
                   FIRST and bypass this per-category cap so a single noisy
                   category never silently buries a high-impact story.
  --manifest PATH  Write a JSON manifest of the drafts created this run to
                   PATH. editor_grade.py --manifest PATH then grades ONLY
                   those, so grading work stays bounded per run.
  --time-budget S  Stop generating once S wall-clock seconds have elapsed;
                   remaining items are deferred to a later run. 0 = unlimited.
  --cli-timeout S  Per `claude -p` call timeout (default: 180s). One slow
                   call can never hang the whole job.
  --urgent-only    Only draft items matching URGENT_TERMS. Used by the
                   second daily "Tier-1 urgent" Hermes ingest so it does
                   NOT spam non-urgent content into the editor PR.
  --tier1-only     Restrict candidate categories to the Tier-1 set
                   (immigration, tax, health, economy). Pairs with
                   --urgent-only for the urgent-ingest job.

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
import time
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

DEFAULT_MAX_DRAFTS = 24
DEFAULT_MAX_PER_CATEGORY = 3
DEFAULT_MAX_ITEMS_PER_FEED = 6
DEFAULT_MODEL = "claude-sonnet-4-6"
DEFAULT_CLI_TIMEOUT = 180  # per `claude -p` call, seconds

VALID_CATEGORIES = {
    "immigration", "tax", "health", "education",
    "retirement", "community", "real-estate", "economy",
    "ai", "robotics",
}

# GSC-backed editorial focus (2026-05-29): Search Console showed real
# impressions/clicks for USCIS/immigration pages. Daily ingest should spend
# Claude time FIRST on Korean-American service journalism: immigration/USCIS,
# tax/IRS, retirement/Social Security/Medicare-adjacent planning, housing,
# insurance/health coverage, and practical settlement/life guides.
# Economy and AI/robotics must continue, but as a maintained secondary lane —
# not as generic market/tech filler that crowds out high-intent service topics.
CATEGORY_PRIORITY = {
    "immigration": 0,
    "tax": 1,
    "retirement": 2,
    "real-estate": 3,
    "health": 4,      # includes insurance / Medicare / ACA / public health
    "community": 5,   # practical Korean-American life guides
    "economy": 6,
    "ai": 7,
    "robotics": 8,
    "education": 9,
}
PRIMARY_FOCUS_CATEGORIES = {"immigration", "tax", "retirement", "real-estate", "health", "community"}
SECONDARY_MAINTAIN_CATEGORIES = {"economy", "ai", "robotics"}

# Tier-1 high-impact categories. The second daily "urgent" ingest restricts
# itself to these so it catches things like USCIS adjustment-of-status policy
# memos, IRS changes, health/insurance alerts, and rate/CPI shocks.
TIER1_CATEGORIES = {"immigration", "tax", "health", "economy", "retirement", "real-estate", "community"}

# Patterns that mark an item as "urgent / high-impact" for Korean-American
# readers. Matched case-insensitively against title + summary. Items that
# match bypass the per-category cap during selection so a single noisy
# feed never crowds out a real policy story.
#
# Editorial review (editor_grade.py) still grades urgent items against the
# same rubric, so a false-positive urgent match becomes a draft, not a
# publish.
URGENT_TERMS = [
    # Immigration
    r"\buscis\b", r"green\s*card", r"adjustment of status",
    r"\bi-?485\b", r"\bi-?130\b", r"\bi-?765\b", r"\bi-?864\b",
    r"policy memo", r"\bvisa bulletin\b", r"visa processing", r"visa interview",
    r"immigrant visa", r"nonimmigrant visa", r"student visa", r"work visa",
    r"deport", r"asylum", r"\bdaca\b", r"travel ban",
    r"\bopt\b", r"\bh-?1b\b", r"\beb-?[1-5]\b", r"\btps\b",
    # Tax
    r"irs guidance", r"tax deadline", r"\b1099\b", r"withholding",
    r"tax credit", r"refund delay", r"\bw-?2\b", r"\bfbar\b",
    # Health
    r"fda recall", r"\bmedicare\b", r"medicaid", r"\baca\b", r"obamacare",
    r"vaccine", r"outbreak", r"\bcdc\b advisory",
    # Economy / benefits / housing / insurance
    r"social security", r"\bcpi\b", r"interest rate",
    r"fed (?:raises|cuts|holds|hike|cut|funds rate)",
    r"unemployment", r"\bfomc\b", r"recession", r"inflation report",
    r"mortgage", r"home insurance", r"health insurance", r"\baca\b",
    r"medicare premium", r"social security cola", r"\bssi\b",
    # Geopolitical / energy / travel shocks that hit Korean-American households
    r"\biran\b", r"\bisrael\b", r"\bhormuz\b", r"strait of hormuz",
    r"middle east", r"missile", r"drone attack", r"airstrike", r"ceasefire",
    r"oil shock", r"crude oil", r"gas prices?", r"gasoline", r"travel advisory",
    r"state department", r"do not travel", r"flight disruptions?",
]
URGENT_RE = re.compile("|".join(URGENT_TERMS), re.IGNORECASE)


def is_urgent(item: "FeedItem") -> bool:
    """True if title or summary matches any URGENT_TERMS pattern."""
    hay = f"{item.title}\n{item.summary}"
    return bool(URGENT_RE.search(hay))


def matches_pattern(item: "FeedItem", pattern: re.Pattern | None) -> bool:
    if not pattern:
        return False
    hay = f"{item.title}\n{item.summary}"
    return bool(pattern.search(hay))


# Viral-topic boost: scripts/discover_viral_topics.py writes the day's
# bursting topic clusters to this file. Matching items get urgent-level
# selection priority. The file is advisory only — stale (>36h) or broken
# files are ignored, and editor grading still gates quality afterward.
VIRAL_BOOST_FILE = REPO / "scripts" / "state" / "viral_boost_terms.json"
VIRAL_BOOST_MAX_AGE_HOURS = 36


def load_viral_boost() -> re.Pattern | None:
    if not VIRAL_BOOST_FILE.exists():
        return None
    try:
        data = json.loads(VIRAL_BOOST_FILE.read_text(encoding="utf-8"))
        generated = datetime.fromisoformat(data["generated_at"])
        age_h = (datetime.now(timezone.utc) - generated).total_seconds() / 3600
        if age_h > VIRAL_BOOST_MAX_AGE_HOURS:
            print(f"↩️  viral boost file is {age_h:.0f}h old — ignoring", file=sys.stderr)
            return None
        terms = [t for c in data.get("clusters", []) for t in c.get("terms", [])]
        if not terms:
            return None
        names = ", ".join(c["name"] for c in data["clusters"])
        print(f"🔥 viral boost active: {names}")
        return re.compile("|".join(terms), re.IGNORECASE)
    except (json.JSONDecodeError, KeyError, ValueError, re.error) as e:
        print(f"⚠️  ignoring broken viral boost file: {e}", file=sys.stderr)
        return None


CATEGORY_RELEVANCE_TERMS = {
    # Economy must stay active, but avoid generic corporate/media/market gossip.
    "economy": re.compile(
        r"inflation|\bcpi\b|interest rate|federal reserve|\bfed\b|jobs?|wages?|"
        r"unemployment|recession|tariff|mortgage|housing|rent|consumer|"
        r"small business|retirement|401\(k\)|ira|tax|irs|social security|"
        r"credit|debt|insurance|affordability|prices?|"
        r"iran|israel|hormuz|middle east|missile|airstrike|ceasefire|"
        r"oil|crude|gasoline|gas prices?|travel advisory|do not travel|flight", 
        re.IGNORECASE,
    ),
    # AI/robotics stay, but should connect to work, automation, small business,
    # education/careers, safety, or investment/market concentration.
    "ai": re.compile(
        r"\bai\b|artificial intelligence|agent|automation|jobs?|work|career|"
        r"small business|startup|education|school|coding|robot|labor|market|"
        r"investment|chip|data center",
        re.IGNORECASE,
    ),
    "robotics": re.compile(
        r"robot|robotics|automation|warehouse|factory|labor|jobs?|care|health|"
        r"restaurant|small business|humanoid|physical ai",
        re.IGNORECASE,
    ),
}


def is_category_relevant(item: "FeedItem") -> bool:
    """Filter out low-utility secondary-lane filler without disabling lanes."""
    pattern = CATEGORY_RELEVANCE_TERMS.get(item.category)
    if not pattern:
        return True
    hay = f"{item.title}\n{item.summary}"
    return bool(pattern.search(hay))

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
        title = strip_html(entry.get("title") or "").strip()
        if not link or not title:
            continue
        canonical = canonical_url(link)
        parsed_link = urlparse(canonical)
        if parsed_link.scheme not in ("http", "https") or not parsed_link.netloc:
            print(f"⚠️  {name}: skipping invalid link for {title[:60]!r}: {link[:120]!r}", file=sys.stderr)
            continue
        if "<" in link or ">" in link or "%3c" in canonical.lower() or "%3e" in canonical.lower():
            print(f"⚠️  {name}: skipping HTML-looking link for {title[:60]!r}: {link[:120]!r}", file=sys.stderr)
            continue
        summary = strip_html(entry.get("summary") or entry.get("description") or "")
        published = entry.get("published") or entry.get("updated") or ""
        items.append(FeedItem(
            source_name=name,
            category=category,
            title=title,
            url=link,
            canonical_url=canonical,
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
- Editorial focus for tomorrow and ongoing daily ingest, based on GSC evidence:
  USCIS/immigration pages are already earning impressions/clicks, so prioritize
  immigration/USCIS, tax/IRS, retirement/Social Security, housing/mortgage,
  insurance/Medicare/ACA, and practical Korean-American life-guide topics.
  Economy and AI/robotics must CONTINUE as maintained lanes, especially when
  they affect jobs, small business, markets, or automation risk, but do not let
  generic economy/tech items crowd out high-intent service journalism.
- Output is Markdown ONLY (no code fences around the whole thing, no
  preamble, no postscript).
- Output starts with YAML frontmatter delimited by --- lines, then body.
- Direct quotes from the source must each be 25 Korean characters or
  fewer (or ~15 English words). Paraphrase the rest. Never copy whole
  sentences verbatim.
- Every factual claim must be traceable to the source provided. Do NOT
  introduce numbers, names, or events not present in the source.
- Add original editorial synthesis using only source-grounded facts: explain
  concrete implications for Korean-American readers instead of merely
  translating/summarizing the source.
- Visualization is Migukstory's core differentiation. Every draft must include
  at least one useful visual explanation: Mermaid flowchart for processes/
  eligibility paths, timeline/stage list for date-driven changes, or Markdown
  comparison table for old-vs-new/options/risks. The visual must be accurate,
  mobile-readable, and not decorative filler.
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

[4~6문단의 한국어 본문. 한 문단당 2~4문장. 직접 인용은 25자 이내.
숫자/날짜/이름은 원문에 있는 것만 사용.
반드시 한 문단은 "미주 한인에게 왜 중요한가"를 구체적으로 다루세요:
한인 자영업자, 유학생, 취업비자/영주권자, 은퇴자, 부모 세대, 한인 가정 중
해당되는 독자 그룹을 골라 실제 의사결정·서류·세금·건강·생활비·커뮤니티
영향을 설명하세요. AI/robotics 카테고리는 일자리, 소상공인 자동화, 자녀 교육·진로,
투자 위험, 이민자 노동자, 한인 가정 영향 중 원문에서 논리적으로 이어지는 축으로
풀어 쓰세요. 단, 원문에 없는 새로운 사실은 금지하고 원문 사실에서
논리적으로 따라오는 영향 분석만 하세요.]

## 핵심 요약

- [핵심 포인트 1]
- [핵심 포인트 2]
- [핵심 포인트 3]

## 한눈에 보는 변화

[기사 성격에 맞게 반드시 하나 이상 포함하세요:
- 절차/자격/신청 흐름이면 번호 매긴 단계별 체크리스트 또는 Markdown 표
- 날짜/단계 변화면 짧은 타임라인 또는 단계별 카드 목록
- 기존/변경/선택지 비교면 Markdown 비교표
금지: Mermaid, flowchart/graph, sequenceDiagram, gantt 등 코드형 다이어그램. 사이트에서 깨질 수 있으므로 발행용 초안에는 절대 넣지 마세요.
시각화는 원문 사실에 근거해야 하며, 모바일에서 읽히도록 짧은 한국어 라벨을 사용하세요.]

## 출처 (Sources)

- [{source_name}]({canonical_url})
"""


def _build_user_prompt(item: FeedItem) -> str:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return PROMPT_USER_TEMPLATE.format(
        source_name=item.source_name,
        category=item.category,
        title=item.title,
        canonical_url=item.canonical_url,
        published=item.published or "(원문 미명시)",
        summary=item.summary or "(요약 없음 — 제목과 링크만 사용)",
        today=today,
    )


def _call_claude_via_cli(item: FeedItem, cli_timeout: int) -> str:
    """Call `claude -p` (uses local Max-subscription auth, no API key)."""
    import subprocess
    user_prompt = _build_user_prompt(item)
    # claude -p takes a single prompt; combine system + user inline.
    combined = (
        PROMPT_SYSTEM
        + "\n\nRespond with the markdown content only. Do NOT use any tools.\n\n"
        + user_prompt
    )
    try:
        result = subprocess.run(
            ["claude", "-p", combined, "--output-format", "text"],
            capture_output=True, text=True, check=True,
            timeout=cli_timeout, stdin=subprocess.DEVNULL,
        )
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"claude -p timed out ({cli_timeout}s)")
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"claude -p failed (exit {e.returncode}): {(e.stderr or '')[:300]}")
    except FileNotFoundError:
        sys.exit("❌ `claude` CLI not found in PATH. Install Claude Code or run on a host that has it.")


def _call_claude_via_api(item: FeedItem, model: str) -> str:
    """Original code path — calls api.anthropic.com directly. Needs ANTHROPIC_API_KEY."""
    try:
        from anthropic import Anthropic
    except ImportError:
        sys.exit("❌ anthropic SDK missing. Run: pip install -r scripts/requirements-draft.txt")
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        sys.exit("❌ ANTHROPIC_API_KEY is not set. "
                 "Set it in your shell or GitHub Secrets, OR set CLAUDE_VIA_CLI=1 to use the "
                 "local `claude` CLI with Max-subscription auth instead. "
                 "For testing without either, pass --dry-run.")
    client = Anthropic(api_key=api_key)
    msg = client.messages.create(
        model=model,
        max_tokens=2400,
        system=PROMPT_SYSTEM,
        messages=[{"role": "user", "content": _build_user_prompt(item)}],
    )
    parts = [b.text for b in msg.content if getattr(b, "type", None) == "text"]
    return "".join(parts).strip()


def call_claude(item: FeedItem, model: str, cli_timeout: int) -> str:
    """Route to API or CLI based on CLAUDE_VIA_CLI env var.

    Set CLAUDE_VIA_CLI=1 to invoke local `claude -p` (Max auth, no API key).
    Default: use Anthropic API (ANTHROPIC_API_KEY required).
    """
    if os.environ.get("CLAUDE_VIA_CLI", "").strip() == "1":
        return _call_claude_via_cli(item, cli_timeout)
    return _call_claude_via_api(item, model)


def deterministic_draft(item: FeedItem) -> str:
    """Source-only emergency draft when Claude Code auth/API is unavailable.

    This keeps Claude as the primary path, but prevents a total zero-post day
    when Claude returns 401/timeout. The output is intentionally conservative:
    it uses only the RSS title/summary/source URL, avoids invented facts, and
    must still pass deterministic_queue_fallback.py before publication.
    """
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    title_src = strip_html(item.title).strip() or "미국 생활 업데이트"
    source_summary = strip_html(item.summary).strip()
    if not source_summary:
        source_summary = "원문 RSS에는 제목 중심의 짧은 알림만 제공됐습니다. 따라서 이 글은 원문에 확인된 제목·출처 정보와 공식 확인 경로 중심으로 정리합니다."
    safe_summary = source_summary[:900]
    korean_title = title_src
    if not re.search(r"[가-힣]", korean_title):
        category_prefix = {
            "immigration": "이민 업데이트",
            "tax": "세금 업데이트",
            "health": "건강·안전 업데이트",
            "real-estate": "주택·모기지 업데이트",
            "retirement": "은퇴·복지 업데이트",
            "community": "한인 생활 업데이트",
            "economy": "경제 업데이트",
            "ai": "AI·일자리 업데이트",
            "robotics": "로봇·미래직업 업데이트",
            "education": "교육 업데이트",
        }.get(item.category, "미국 생활 업데이트")
        korean_title = f"{category_prefix}: {title_src}"
    desc = f"{title_src} 관련 소식입니다. 미주 한인 독자가 확인해야 할 영향, 체크포인트, 공식 확인 경로를 정리했습니다."
    tags = [item.category, "미주한인", "체크리스트", "업데이트"]
    if item.category == "tax":
        tags.insert(0, "IRS")
    if item.category == "immigration":
        tags.insert(0, "USCIS")
    if item.category == "health":
        tags.insert(0, "FDA")
    tags_yaml = ", ".join(repr(t) for t in tags[:6])
    safe_title = korean_title.replace("'", "’")
    safe_desc = desc.replace("'", "’")[:220]
    safe_source = item.source_name.replace("'", "’")
    table_title = title_src.replace("|", "/")
    return f"""---
title: '{safe_title}'
description: '{safe_desc}'
pubDate: '{today}'
tags: [{tags_yaml}]
category: '{item.category}'
ageGroup: 'all'
draft: false
source: '{safe_source}'
sourceUrl: '{item.canonical_url}'
---

# {korean_title}

{safe_summary}

이번 소식은 미주 한인 가정, 유학생, 직장인, 자영업자에게 바로 확인이 필요한 생활 정보입니다. 원문 RSS가 제공한 정보 범위가 제한적이기 때문에, 아래 내용은 확인된 제목·요약·출처를 바탕으로 **무엇을 확인해야 하는지** 중심으로 정리합니다. 법률·세금·의료 판단이 필요한 경우에는 전문가 상담을 권장합니다.

## 한눈에 보는 체크포인트

| 구분 | 지금 확인할 내용 | 한인 독자에게 중요한 이유 |
|---|---|---|
| 원문 이슈 | {table_title} | 생활비, 신분, 건강, 여행, 사업 운영에 영향을 줄 수 있습니다. |
| 확인 대상 | 공식 발표·기관 안내·원문 업데이트 | RSS 요약만으로 세부 조건을 단정하면 위험합니다. |
| 오늘 할 일 | 본인 상황에 해당하는 날짜·지역·자격·상품명을 대조 | 같은 뉴스라도 비자, 세금, 보험, 거주 주에 따라 영향이 달라집니다. |
| 주의점 | SNS 요약보다 공식 링크 우선 확인 | 잘못된 정보로 신청·결제·여행 결정을 하면 손해가 커질 수 있습니다. |

## 미주 한인이 봐야 할 영향

첫째, 이 소식이 본인이나 가족에게 직접 적용되는지 확인해야 합니다. 이민·세금·건강·주택·여행 관련 뉴스는 제목은 단순해 보여도 실제 적용 대상, 날짜, 지역, 자격 조건이 따로 붙는 경우가 많습니다.

둘째, 자영업자나 직장인은 업무상 영향도 함께 봐야 합니다. 직원 안내, 고객 공지, 회계·보험 서류, 여행 일정, 공급망 확인처럼 개인 생활을 넘어 사업 운영에 연결될 수 있습니다.

셋째, 원문이 업데이트될 가능성을 열어두어야 합니다. 특히 정부기관, 법원, 보건·여행 경보, 세금 마감 관련 사안은 하루 사이에도 세부 안내가 바뀔 수 있습니다.

## 오늘 확인 순서

1. 원문 링크에서 최신 업데이트 시간을 확인합니다.
2. 본인에게 해당하는 주(state), 비자/신분, 세금연도, 보험/상품명, 여행 목적지를 대조합니다.
3. 마감일이나 시행일이 있는 경우 캘린더에 따로 표시합니다.
4. 비용, 신분, 건강, 법률 판단이 걸리면 전문가 상담을 권장합니다.

## 출처 (Sources)

- {item.source_name}: {item.canonical_url}
"""


def write_manifest(path: Path, drafts: list[Path]) -> None:
    """Record the drafts created this run so editor_grade.py can grade only them."""
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "run_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "drafts": [str(p.relative_to(REPO)) if p.is_relative_to(REPO) else str(p)
                   for p in drafts],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")


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
    p.add_argument("--max-drafts", type=int, default=DEFAULT_MAX_DRAFTS,
                   help=f"Global cap for drafts this run. Default: {DEFAULT_MAX_DRAFTS}.")
    p.add_argument("--max-per-category", type=int, default=DEFAULT_MAX_PER_CATEGORY,
                   help=f"Target cap per category. Default: {DEFAULT_MAX_PER_CATEGORY}.")
    p.add_argument("--manifest", metavar="PATH",
                   help="Write a JSON manifest of drafts created this run to PATH.")
    p.add_argument("--time-budget", type=int, default=0,
                   help="Wall-clock budget in seconds; remaining items are deferred. "
                        "Default: 0 (unlimited).")
    p.add_argument("--cli-timeout", type=int, default=DEFAULT_CLI_TIMEOUT,
                   help=f"Per `claude -p` call timeout, seconds. Default: {DEFAULT_CLI_TIMEOUT}.")
    p.add_argument("--urgent-only", action="store_true",
                   help="Restrict candidates to URGENT_TERMS matches only "
                        "(second daily Tier-1 ingest).")
    p.add_argument("--tier1-only", action="store_true",
                   help="Restrict candidate categories to "
                        f"{sorted(TIER1_CATEGORIES)}.")
    p.add_argument("--deterministic-on-claude-fail", action="store_true",
                   help="Emergency source-only draft fallback when Claude CLI/API fails. "
                        "Drafts still require deterministic_queue_fallback.py before publication.")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    max_drafts = max(1, args.max_drafts)
    max_per_category = max(1, args.max_per_category)
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
            if not is_category_relevant(item):
                print(f"↩️  {src['name']}: skipping low-utility {item.category} item: {item.title[:80]}")
                continue
            candidates.append(item)

    if not candidates:
        print("✅ Nothing new — all feed items already seen.")
        return 0

    viral_boost_re = load_viral_boost()

    if args.tier1_only:
        before = len(candidates)
        candidates = [c for c in candidates if c.category in TIER1_CATEGORIES]
        print(f"🎯 --tier1-only: kept {len(candidates)}/{before} candidates "
              f"in categories {sorted(TIER1_CATEGORIES)}")

    if args.urgent_only:
        before = len(candidates)
        candidates = [c for c in candidates if is_urgent(c) or matches_pattern(c, viral_boost_re)]
        print(f"🚨 --urgent-only: kept {len(candidates)}/{before} URGENT/viral candidates")
        if not candidates:
            print("✅ No urgent candidates this run — nothing to draft.")
            return 0

    # Urgent items get picked FIRST (up to max_drafts) so a per-category cap
    # never silently drops, e.g., a USCIS adjustment-of-status policy memo
    # because that day already had two unrelated immigration items.
    selected: list[FeedItem] = []
    urgent_picks: list[FeedItem] = []
    remaining: list[FeedItem] = []
    for c in candidates:
        if is_urgent(c) or matches_pattern(c, viral_boost_re):
            urgent_picks.append(c)
        else:
            remaining.append(c)
    urgent_by_source: dict[str, list[FeedItem]] = {}
    for it in urgent_picks:
        urgent_by_source.setdefault(it.source_name, []).append(it)
    while len(selected) < max_drafts and any(urgent_by_source.values()):
        for name in sorted(urgent_by_source):
            bucket = urgent_by_source[name]
            if not bucket:
                continue
            selected.append(bucket.pop(0))
            if len(selected) >= max_drafts:
                break

    # Round-robin the rest by category, respecting max_per_category. Categories
    # are ordered by the GSC-backed editorial focus: high-intent service topics
    # first, economy/AI/robotics maintained afterward.
    by_category_source: dict[str, dict[str, list[FeedItem]]] = {}
    for c in remaining:
        by_category_source.setdefault(c.category, {}).setdefault(c.source_name, []).append(c)
    category_quota_used: dict[str, int] = {}
    for it in selected:
        category_quota_used[it.category] = category_quota_used.get(it.category, 0) + 1

    for category in sorted(by_category_source, key=lambda c: (CATEGORY_PRIORITY.get(c, 99), c)):
        picked_for_category = category_quota_used.get(category, 0)
        by_source = by_category_source[category]
        while picked_for_category < max_per_category and len(selected) < max_drafts and any(by_source.values()):
            for name in sorted(by_source):
                if not by_source[name]:
                    continue
                selected.append(by_source[name].pop(0))
                picked_for_category += 1
                if picked_for_category >= max_per_category or len(selected) >= max_drafts:
                    break

    urgent_in_selected = sum(1 for s in selected if is_urgent(s))
    viral_in_selected = sum(1 for s in selected if matches_pattern(s, viral_boost_re))
    primary_focus_selected = sum(1 for s in selected if s.category in PRIMARY_FOCUS_CATEGORIES)
    secondary_maintained_selected = sum(1 for s in selected if s.category in SECONDARY_MAINTAIN_CATEGORIES)
    print(f"\n🎯 Planning {len(selected)} draft(s) "
          f"(max {max_drafts}, max/category {max_per_category}, "
          f"urgent-prio {urgent_in_selected}, viral-prio {viral_in_selected}, "
          f"primary-focus {primary_focus_selected}, "
          f"economy/AI/robotics maintained {secondary_maintained_selected}):")
    for it in selected:
        urgent = is_urgent(it)
        viral = matches_pattern(it, viral_boost_re)
        flag = "🚨🔥" if urgent and viral else "🚨" if urgent else "🔥" if viral else "  "
        print(f"   {flag} [{it.category}] {it.source_name}: {it.title[:80]}")

    if args.dry_run:
        print("\n🧪 --dry-run: skipping Claude calls and file writes.")
        return 0

    DRAFTS.mkdir(parents=True, exist_ok=True)

    written: list[Path] = []
    failures: list[tuple[FeedItem, str]] = []
    deferred = 0
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    start = time.monotonic()

    for idx, item in enumerate(selected):
        if args.time_budget and (time.monotonic() - start) > args.time_budget:
            deferred = len(selected) - idx
            print(f"\n⏱  Time budget ({args.time_budget}s) exhausted — "
                  f"deferring {deferred} item(s) to a later run.")
            break
        print(f"\n🤖 Generating: {item.title[:80]}")
        try:
            md = call_claude(item, model=model, cli_timeout=args.cli_timeout)
        except SystemExit:
            raise
        except Exception as e:
            if args.deterministic_on_claude_fail:
                print(f"   ⚠️ Claude call failed, using deterministic emergency draft: {e}", file=sys.stderr)
                md = deterministic_draft(item)
            else:
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

    # Record this run's drafts so editor_grade.py can grade only them.
    if args.manifest:
        write_manifest(Path(args.manifest), written)
        print(f"📝 Manifest ({len(written)} draft(s)): {args.manifest}")

    print(f"\n📊 Wrote {len(written)} draft(s); {len(failures)} failure(s); "
          f"{deferred} deferred.")
    for it, why in failures:
        print(f"   ! {it.source_name} :: {it.title[:60]} — {why}")

    return 0 if written or not failures else 1


if __name__ == "__main__":
    sys.exit(main())
