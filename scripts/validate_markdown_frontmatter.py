#!/usr/bin/env python3
"""Deterministic markdown/frontmatter validator for Miguk Story.

Purpose: catch malformed Astro content before a queue publish commits broken
markdown to main. It intentionally avoids third-party packages so it can run in
GitHub Actions without pip install.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

REPO = Path(__file__).resolve().parent.parent
DEFAULT_PATHS = [REPO / "queue", REPO / "drafts", REPO / "src" / "content" / "blog"]
REQUIRED_FIELDS = ("title", "description", "pubDate", "category")
URL_FIELDS = ("sourceUrl", "canonicalUrl")
VALID_CATEGORIES = {
    "immigration",
    "tax",
    "economy",
    "ai",
    "robotics",
    "health",
    "education",
    "retirement",
    "community",
    "real-estate",
}


def iter_markdown(paths: list[Path]) -> list[Path]:
    files: list[Path] = []
    for path in paths:
        if not path.exists():
            continue
        if path.name.upper() == "README.MD":
            continue
        if path.is_file() and path.suffix in {".md", ".mdx"}:
            files.append(path)
        elif path.is_dir():
            files.extend(sorted(
                p for p in path.rglob("*")
                if p.suffix in {".md", ".mdx"} and p.name.upper() != "README.MD"
            ))
    return sorted(set(files))


def split_frontmatter(text: str) -> tuple[list[str], str | None]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return [], "missing opening --- frontmatter delimiter"
    for idx, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return lines[1:idx], None
    return [], "missing closing --- frontmatter delimiter"


def quote_state(value: str) -> str | None:
    """Return an error if a scalar starts quoted but does not close on the same line."""
    stripped = value.strip()
    if not stripped:
        return None
    quote = stripped[0]
    if quote not in {"'", '"'}:
        # Catch stray odd quotes in common incident shape: sourceUrl: 'https://...)
        if stripped.count("'") % 2 == 1 or stripped.count('"') % 2 == 1:
            return "unbalanced quote in scalar value"
        return None
    escaped = False
    for ch in stripped[1:]:
        if quote == '"' and ch == "\\" and not escaped:
            escaped = True
            continue
        if ch == quote and not escaped:
            return None
        escaped = False
    return f"unclosed {quote} quote"


def parse_simple_fields(frontmatter: list[str]) -> dict[str, str]:
    fields: dict[str, str] = {}
    for raw in frontmatter:
        if not raw.strip() or raw.lstrip().startswith("#") or raw.startswith((" ", "\t", "-")):
            continue
        if ":" not in raw:
            continue
        key, value = raw.split(":", 1)
        fields[key.strip()] = value.strip()
    return fields


def unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def validate_file(path: Path, strict_publish: bool) -> list[str]:
    rel = path.relative_to(REPO) if path.is_relative_to(REPO) else path
    text = path.read_text(encoding="utf-8")
    frontmatter, err = split_frontmatter(text)
    if err:
        return [f"{rel}: {err}"]

    errors: list[str] = []
    for line_no, raw in enumerate(frontmatter, start=2):
        if not raw.strip() or raw.lstrip().startswith("#") or raw.startswith((" ", "\t", "-")):
            continue
        if ":" not in raw:
            errors.append(f"{rel}:{line_no}: frontmatter line is not key: value")
            continue
        key, value = raw.split(":", 1)
        qerr = quote_state(value)
        if qerr:
            errors.append(f"{rel}:{line_no}: {key.strip()}: {qerr}")

    fields = parse_simple_fields(frontmatter)
    for required in REQUIRED_FIELDS:
        if required not in fields or not unquote(fields[required]):
            errors.append(f"{rel}: missing required frontmatter field: {required}")

    category = unquote(fields.get("category", ""))
    if category and category not in VALID_CATEGORIES:
        errors.append(f"{rel}: invalid category '{category}'")

    for field in URL_FIELDS:
        if field not in fields:
            continue
        value = unquote(fields[field])
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            errors.append(f"{rel}: invalid {field}: {value}")

    if strict_publish and path.parts and "queue" in path.parts:
        if "sourceUrl" not in fields or not unquote(fields.get("sourceUrl", "")):
            errors.append(f"{rel}: queue item missing sourceUrl")
        if "## 핵심 요약" not in text:
            errors.append(f"{rel}: queue item missing ## 핵심 요약")
        if "## 출처 (Sources)" not in text:
            errors.append(f"{rel}: queue item missing ## 출처 (Sources)")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*", help="Files or directories to validate. Defaults to queue, drafts, and blog content.")
    parser.add_argument("--strict-publish", action="store_true", help="Apply stricter rules to queue/ files before publication.")
    args = parser.parse_args()

    paths = [Path(p).resolve() for p in args.paths] if args.paths else DEFAULT_PATHS
    files = iter_markdown(paths)
    errors: list[str] = []
    for path in files:
        errors.extend(validate_file(path, strict_publish=args.strict_publish))

    if errors:
        print("❌ Markdown/frontmatter validation failed:", file=sys.stderr)
        for error in errors:
            print(f" - {error}", file=sys.stderr)
        return 1

    print(f"✅ Markdown/frontmatter validation passed ({len(files)} file(s)).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
