#!/usr/bin/env python3
"""
Deterministic topic-duplicate detection against already-published posts.

Why: on 6/29 and 6/30 the pipeline published two near-identical Medicare
GLP-1 articles (same program, same $50 copay, same audience) because nothing
compared a new draft against what the site already ran. Duplicate topics
cannibalize each other in search and read as sloppy editing.

How: token-Jaccard similarity on the title AND on the slug versus every
published post in src/content/blog/. Tokens are latin/digit runs plus Korean
syllable runs, minus high-frequency editorial stopwords (월, 가이드, 한인…)
that would otherwise make every service headline look alike. The GLP-1 pair
scores ~0.64 title / ~0.83 slug under this metric; unrelated service posts
score well under 0.3. Threshold 0.5 keeps the gate conservative — it should
only fire on true re-runs of the same story.

Used by editor_grade.py (caps score below the auto-promote threshold) and
publish_from_queue.py (hard-fails the publish safety gate).
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BLOG = REPO / "src" / "content" / "blog"

SIMILARITY_THRESHOLD = 0.5

# Editorial boilerplate that appears in most Korean service headlines/slugs —
# excluded so similarity reflects the actual story, not the house style.
STOPWORDS = {
    "월", "일", "년", "주", "시", "및", "등", "수", "것", "그", "이", "저",
    "한인", "미국", "가이드", "정리", "총정리", "완전", "완벽", "핵심",
    "확인", "방법", "시작", "시행", "시대", "변경", "발표", "최신",
    "korean", "koreans", "guide", "2024", "2025", "2026", "2027",
    "the", "a", "an", "and", "or", "of", "for", "to", "in", "on",
}


def _tokens(text: str) -> set[str]:
    raw = re.findall(r"[A-Za-z0-9]+|[가-힣]+", text.lower())
    return {t for t in raw if len(t) > 1 or t.isdigit()} - STOPWORDS


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _title_of(md_text: str) -> str:
    m = re.search(r"^title:\s*['\"]?(.+?)['\"]?\s*$", md_text[:2000], re.MULTILINE)
    return m.group(1) if m else ""


def find_topic_duplicate(
    title: str,
    slug: str,
    blog_dir: Path = BLOG,
    threshold: float = SIMILARITY_THRESHOLD,
    exclude_slug: str | None = None,
) -> tuple[str, float] | None:
    """Return (existing_slug, similarity) of the closest published post at or
    above `threshold`, else None. `exclude_slug` skips the post itself when
    re-grading something already in blog/."""
    new_title_tokens = _tokens(title)
    new_slug_tokens = _tokens(slug)
    best: tuple[str, float] | None = None
    if not blog_dir.exists():
        return None
    for path in blog_dir.glob("*.md"):
        existing_slug = path.stem
        if exclude_slug and existing_slug == exclude_slug:
            continue
        try:
            head = path.read_text(encoding="utf-8", errors="ignore")[:2000]
        except OSError:
            continue
        sim = max(
            _jaccard(new_title_tokens, _tokens(_title_of(head))),
            _jaccard(new_slug_tokens, _tokens(existing_slug)),
        )
        if sim >= threshold and (best is None or sim > best[1]):
            best = (existing_slug, sim)
    return best
