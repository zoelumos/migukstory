#!/usr/bin/env python3
"""
Publish-from-queue daily script for migukstory.com.

Picks the first .md file from /queue/ alphabetically (oldest by filename),
updates its `pubDate` to today, and moves it to src/content/blog/.

Designed to be run via GitHub Actions cron. No API key, no LLM call required.
Content is pre-generated; this script just schedules publication.

Env vars (optional):
    POSTS_PER_RUN — int (default: 1)
"""

import os
import re
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
QUEUE = REPO / "queue"
BLOG = REPO / "src" / "content" / "blog"

FORBIDDEN_VISUAL_PATTERNS = (
    "```mermaid",
    "flowchart ",
    "graph ",
    "sequenceDiagram",
    "gantt",
)

REVIEW_MARKERS = (
    "편집 보류 메모",
    "needs-review",
    "Steve 지적",
)


def validate_publishable(content: str, src: Path) -> None:
    """Final non-LLM safety gate before queue/ files become live posts.

    Editorial review should catch these earlier, but publish is the last
    irreversible step before RSS/sitemap exposure. Keep this deterministic and
    conservative.
    """
    failures: list[str] = []
    if any(pattern in content for pattern in FORBIDDEN_VISUAL_PATTERNS):
        failures.append("forbidden code-style diagram/Mermaid found")
    if any(marker in content for marker in REVIEW_MARKERS):
        failures.append("review-hold marker found")
    if re.search(r"2024년\s*기준", content) and re.search(r"(절반|기본 생활비|financial edge|households)", content, re.I):
        failures.append("stale 2024 household-affordability framing requires human rewrite")
    required = ["## 핵심 요약", "## 출처 (Sources)"]
    for marker in required:
        if marker not in content:
            failures.append(f"missing required section: {marker}")
    if not re.search(r"^sourceUrl:\s*['\"]?https?://", content, flags=re.MULTILINE):
        failures.append("missing sourceUrl")
    if failures:
        raise ValueError(f"publish safety gate failed for {src.name}: " + "; ".join(failures))


def update_pub_date(content: str, new_date: str) -> str:
    """Replace pubDate in frontmatter."""
    return re.sub(
        r"^pubDate:\s*['\"]?[^'\"\n]+['\"]?",
        f"pubDate: '{new_date}'",
        content,
        count=1,
        flags=re.MULTILINE,
    )


def mark_published(content: str) -> str:
    """Ensure a queued draft becomes a real published post.

    Draft files intentionally carry `draft: true` while they sit under drafts/
    or queue/. Once moved to src/content/blog/, leaving that flag behind is
    ambiguous for RSS/sitemap/build-time SEO guards and future content filters.
    """
    if re.search(r"^draft:\s*true\s*$", content, flags=re.MULTILINE):
        return re.sub(r"^draft:\s*true\s*$", "draft: false", content, count=1, flags=re.MULTILINE)
    if not re.search(r"^draft:\s*", content, flags=re.MULTILINE):
        return re.sub(r"^(---\n)", "---\ndraft: false\n", content, count=1)
    return content


def next_queued() -> Path | None:
    """First .md file in queue/ alphabetically."""
    if not QUEUE.exists():
        return None
    md_files = sorted(QUEUE.glob("*.md"))
    return md_files[0] if md_files else None


def publish_one() -> Path | None:
    src = next_queued()
    if not src:
        print("⚠️ Queue is empty — nothing to publish.")
        return None

    dest = BLOG / src.name
    if dest.exists():
        # Slug collision — add today's date to filename
        today_compact = datetime.now(timezone.utc).strftime("%m%d")
        dest = BLOG / f"{src.stem}-{today_compact}.md"

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    content = src.read_text(encoding="utf-8")
    validate_publishable(content, src)
    content = update_pub_date(content, today)
    content = mark_published(content)

    BLOG.mkdir(parents=True, exist_ok=True)
    dest.write_text(content, encoding="utf-8")
    src.unlink()

    print(f"✅ Published: {src.name} → {dest.relative_to(REPO)}")
    print(f"   pubDate set to: {today}")
    return dest


def main():
    runs = int(os.environ.get("POSTS_PER_RUN", "1"))
    for i in range(runs):
        if publish_one() is None:
            break

    remaining = len(list(QUEUE.glob("*.md"))) if QUEUE.exists() else 0
    print(f"\n📦 Queue remaining: {remaining} post(s)")
    if remaining <= 3:
        print(f"⚠️ Low queue (<= 3). Time to add more posts to /queue/.")


if __name__ == "__main__":
    main()
