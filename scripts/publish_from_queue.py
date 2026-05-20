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


def update_pub_date(content: str, new_date: str) -> str:
    """Replace pubDate in frontmatter."""
    return re.sub(
        r"^pubDate:\s*['\"]?[^'\"\n]+['\"]?",
        f"pubDate: '{new_date}'",
        content,
        count=1,
        flags=re.MULTILINE,
    )


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
    content = update_pub_date(content, today)

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
