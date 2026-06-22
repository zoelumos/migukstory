#!/usr/bin/env python3
"""Deterministic fallback reviewer for Miguk Story daily ingest.

This is intentionally conservative. It only promotes drafts to queue/ when the
Claude editor path timed out/failed but the draft still passes objective checks:
frontmatter, sources, no fragile Mermaid/flowchart syntax, explicit Korean-
American angle, visual summary, and high-stakes topic category.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
DRAFTS = REPO / "drafts"
QUEUE = REPO / "queue"
REPORT = REPO / "scripts" / "state" / "deterministic_fallback_report.json"

ALLOWED_CATEGORIES = {"immigration", "health", "tax", "economy", "education", "retirement", "community", "real-estate"}
HIGH_STAKES_TERMS = re.compile(
    r"USCIS|영주권|이민|비자|I-485|신분조정|가족초청|망명|추방|ICE|전쟁|분쟁|공습|휴전|"
    r"우크라이나|가자|이스라엘|중국|북한|대만|CDC|FDA|리콜|경보|살모넬라|대법원|세금|IRS|"
    r"모기지|주택|mortgage|housing|interest rate|travel advisory|여행|중동|naloxone|Medicare|ACA|health insurance",
    re.I,
)
KOREAN_ANGLE_TERMS = re.compile(r"한인|미주|교민|유학생|이민자|자영업|가정|직장인|부모|시니어")
FORBIDDEN_VISUAL = re.compile(r"```mermaid|\bflowchart\b|\bgraph\s+(?:TD|LR|BT|RL)\b|sequenceDiagram|\bgantt\b", re.I)
VISUAL_OK = re.compile(r"##\s*(한눈에 보는|타임라인|체크리스트|비교표)|^\|.+\|\s*\n\|\s*:?-{3,}:?", re.M)
SOURCE_SECTION = re.compile(r"##\s*출처\s*\(Sources\)|##\s*출처")
HTTP_URL = re.compile(r"https?://[^\s)]+")


def parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---", 4)
    if end == -1:
        return {}, text
    raw = text[4:end]
    body = text[end + 4 :]
    data: dict[str, Any] = {}
    for line in raw.splitlines():
        if not line.strip() or line.startswith(" ") or ":" not in line:
            continue
        key, val = line.split(":", 1)
        val = val.strip().strip('"').strip("'")
        data[key.strip()] = val
    return data, body


def load_manifest(path: Path) -> list[Path]:
    try:
        data = json.loads(path.read_text())
    except Exception:
        return []
    out: list[Path] = []
    for item in data.get("drafts", []):
        p = Path(item)
        if not p.is_absolute():
            p = REPO / p
        try:
            p.relative_to(DRAFTS)
        except ValueError:
            continue
        if p.exists() and p.suffix == ".md":
            out.append(p)
    return out


def evaluate(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8", errors="replace")
    fm, body = parse_frontmatter(text)
    title = str(fm.get("title", ""))
    desc = str(fm.get("description", ""))
    category = str(fm.get("category", ""))
    haystack = "\n".join([title, desc, category, body])
    reasons: list[str] = []

    def fail(reason: str) -> dict[str, Any]:
        reasons.append(reason)
        return {"path": str(path.relative_to(REPO)), "action": "keep_draft", "ok": False, "reasons": reasons}

    required = ["title", "description", "pubDate", "category", "tags"]
    missing = [k for k in required if not fm.get(k)]
    if missing:
        return fail(f"missing frontmatter: {', '.join(missing)}")
    if str(fm.get("draft", "")).lower() == "true":
        return fail("draft:true present")
    if category not in ALLOWED_CATEGORIES:
        return fail(f"unknown category: {category}")
    if category == "economy" and not re.search(r"IRS|세금|대법원|전쟁|분쟁|이민|USCIS|리콜|경보", haystack, re.I):
        return fail("generic economy draft is not eligible for fallback promotion")
    if not HIGH_STAKES_TERMS.search(haystack):
        return fail("not high-stakes enough for fallback promotion")
    if not KOREAN_ANGLE_TERMS.search(body):
        return fail("missing explicit Korean-American angle")
    if FORBIDDEN_VISUAL.search(text):
        return fail("forbidden Mermaid/flowchart syntax")
    if not VISUAL_OK.search(text):
        return fail("missing mobile-safe visual/table/checklist section")
    if not SOURCE_SECTION.search(text):
        return fail("missing sources section")
    urls = HTTP_URL.findall(text)
    if not urls:
        return fail("missing source URL")
    if len(body) < 1800:
        return fail("body too thin")
    if "가정의 절반도" in text:
        return fail("known awkward/unsupported phrase present")

    return {
        "path": str(path.relative_to(REPO)),
        "action": "promote",
        "ok": True,
        "reasons": ["deterministic checks passed: sources, KA angle, visual, high-stakes topic"],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--max-promote", type=int, default=3)
    ap.add_argument("--only-if-queue-empty", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    QUEUE.mkdir(exist_ok=True)
    if args.only_if_queue_empty and any(QUEUE.glob("*.md")):
        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "skipped": "queue already has posts",
            "promoted": [],
            "review": [],
        }
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        print("deterministic fallback skipped: queue already has posts")
        return 0

    candidates = load_manifest(Path(args.manifest))
    promoted: list[dict[str, Any]] = []
    review: list[dict[str, Any]] = []
    for p in candidates:
        result = evaluate(p)
        if result["ok"] and len(promoted) < args.max_promote:
            dest = QUEUE / p.name
            result["promoted_to"] = str(dest.relative_to(REPO))
            promoted.append(result)
            if not args.dry_run:
                shutil.move(str(p), str(dest))
        else:
            review.append(result)

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "dry-run" if args.dry_run else "write",
        "promoted": promoted,
        "review": review,
        "counts": {"promoted": len(promoted), "review": len(review)},
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(f"deterministic fallback: {len(promoted)} promoted, {len(review)} kept for review")
    for item in promoted:
        print(f"  ✅ {item['path']} -> {item['promoted_to']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
