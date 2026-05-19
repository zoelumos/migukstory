#!/usr/bin/env python3
"""
Editor agent: grade AI-drafted posts on a 5-axis rubric and auto-promote
high-confidence drafts from drafts/ → queue/ for human one-click merge.

Rubric (0-20 each, total 0-100):
  1. factuality       — claims traceable to ## 출처 (Sources) section
  2. source_diversity — ≥2 distinct publishers in sources
  3. ka_angle         — explicit Korean-American framing (not generic news)
  4. originality      — adds analysis/commentary beyond source summary
  5. structure        — has frontmatter, body, summary bullets, sources

Action thresholds:
  ≥80  → promote: git mv to queue/ (still needs human PR merge, NO auto-publish)
  50-79 → review: stay in drafts/, flagged in report
  <50  → discard_flag: stay in drafts/, marked for likely deletion

Usage:
  python scripts/editor_grade.py [--dry-run] [--threshold 80]

Env:
  ANTHROPIC_API_KEY  required (unless --dry-run)
  ANTHROPIC_MODEL    optional, default: claude-sonnet-4-6 (Haiku 4.5 also fine for cost)

The script writes a report to scripts/state/editor_report.json and (when not
dry-run) moves promoted drafts into queue/. Both the moves and the report are
committed by the calling workflow.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
DRAFTS = REPO / "drafts"
QUEUE = REPO / "queue"
REPORT = REPO / "scripts" / "state" / "editor_report.json"

DEFAULT_MODEL = "claude-sonnet-4-6"
DEFAULT_THRESHOLD = 80
REVIEW_THRESHOLD = 50  # below this = "likely discard"


@dataclass
class Grade:
    slug: str
    score: int                      # 0-100
    scores: dict[str, int]          # per-axis breakdown
    reasoning: str                  # 2-3 sentences from the editor
    action: str                     # promote | review | discard_flag
    promoted_to: str | None = None  # destination path if promoted


SYSTEM_PROMPT = """You are the editor-in-chief of migukstory.com, a Korean-American
community news site. You grade AI-drafted posts on a strict 5-axis rubric before
they're allowed into the publishing queue. Your goal is to protect the site from
Google's helpful-content / spam-update penalties (which target thin AI rewrites
and machine-translated content) AND from publishing factually weak material.

Output is JSON only. No preamble, no postscript, no code fences."""


USER_PROMPT_TEMPLATE = """다음은 사람 검토 전 AI가 작성한 한국어 초안입니다.
편집장으로서 5개 축에 대해 각 0–20점으로 평가하고, 총점(0–100)과 짧은
판단 근거를 한국어로 작성하세요. 결과는 JSON 한 개로만 출력하세요.

## 평가 축 (각 0–20점)

1. **factuality (사실성)**: 본문의 수치·날짜·기관명·인용이 모두 글 끝
   「## 출처 (Sources)」 섹션의 링크로 추적 가능한가? 검증 불가능한 새로운
   사실을 만들어내지 않았는가? 출처 섹션 자체가 비어있거나 부실하면 5점 이하.

2. **source_diversity (출처 다양성)**: 출처 섹션에 **서로 다른 publisher 2곳
   이상**의 1차/반-1차 자료가 인용돼 있는가? 같은 publisher의 여러 페이지만
   인용했다면 10점 이하. 출처 1개만 있으면 5점 이하.

3. **ka_angle (한인 관점)**: 단순 정보 전달이 아니라, 미주 한인 가정·자영업자·
   유학생 등 구체적 한인 그룹에 어떤 의미가 있는지 명시적으로 풀어쓴 분석
   문단이 있는가? 영어 원문을 그냥 번역한 수준이면 5점 이하.

4. **originality (독창성)**: 출처에 단순 의존하지 않고 편집자 차원의 종합·
   비교·맥락 추가가 있는가? 다른 매체가 이미 쓴 것과 차별점이 있는가?
   요약만 있고 분석이 없으면 8점 이하.

5. **structure (구조)**: YAML frontmatter가 완전한가(title, description,
   pubDate, tags, category, ageGroup)? 본문이 3문단 이상이고 「## 핵심 요약」
   불릿 리스트와 「## 출처 (Sources)」 섹션이 있는가? 깨진 마크다운이 없는가?

## 판정 기준

총점이 80 이상이면 자동으로 queue/로 승격되어 사람 한 명이 PR 머지만 누르면
발행됩니다. 따라서 80점 이상은 **사실관계가 명확하고 한인 관점이 살아있는 글**
에만 부여하세요. 의심스러우면 보수적으로 79점 이하를 주세요.

## 입력 초안 (파일명: {slug}.md)

{content}

## 출력 형식 (JSON, 다른 설명 없이)

{{
  "scores": {{
    "factuality": <0-20>,
    "source_diversity": <0-20>,
    "ka_angle": <0-20>,
    "originality": <0-20>,
    "structure": <0-20>
  }},
  "total": <합계 0-100>,
  "reasoning": "<한국어로 2-3문장. 강점과 약점을 모두 언급할 것.>"
}}
"""


def call_claude(slug: str, content: str, model: str) -> tuple[dict, int]:
    try:
        from anthropic import Anthropic
    except ImportError:
        sys.exit("❌ anthropic SDK missing. Run: pip install -r scripts/requirements-draft.txt")
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        sys.exit("❌ ANTHROPIC_API_KEY not set. Set it in env or GitHub Secrets, "
                 "or pass --dry-run for a no-API smoke test.")

    client = Anthropic(api_key=api_key)
    truncated = content if len(content) < 12000 else content[:12000] + "\n…(잘림)"
    user_prompt = USER_PROMPT_TEMPLATE.format(slug=slug, content=truncated)

    msg = client.messages.create(
        model=model,
        max_tokens=900,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )
    text = "".join(b.text for b in msg.content if getattr(b, "type", None) == "text").strip()

    # The model sometimes wraps JSON in ```json fences despite the instruction; strip them.
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.MULTILINE).strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"editor returned non-JSON for {slug}: {e}\n--- raw ---\n{text[:500]}")

    total = int(parsed.get("total") or sum(parsed.get("scores", {}).values()))
    return parsed, total


def grade_one(path: Path, model: str, dry_run: bool) -> Grade:
    slug = path.stem
    content = path.read_text(encoding="utf-8")

    if dry_run:
        # Heuristic stub so we can smoke-test workflow plumbing without API spend.
        sources = content.count("](http")
        score = 60 + min(20, sources * 3)  # crude proxy
        return Grade(
            slug=slug,
            score=score,
            scores={"factuality": 12, "source_diversity": 12, "ka_angle": 12,
                    "originality": 12, "structure": 12},
            reasoning="dry-run heuristic: not a real evaluation",
            action="promote" if score >= DEFAULT_THRESHOLD else "review",
        )

    try:
        parsed, total = call_claude(slug, content, model=model)
    except Exception as e:
        print(f"   ❌ grading failed for {slug}: {e}", file=sys.stderr)
        return Grade(
            slug=slug, score=0, scores={}, reasoning=f"grading error: {e}",
            action="review",
        )

    if total >= DEFAULT_THRESHOLD:
        action = "promote"
    elif total >= REVIEW_THRESHOLD:
        action = "review"
    else:
        action = "discard_flag"

    return Grade(
        slug=slug,
        score=total,
        scores={k: int(v) for k, v in parsed.get("scores", {}).items()},
        reasoning=parsed.get("reasoning", "").strip(),
        action=action,
    )


def promote(path: Path) -> Path:
    """Move drafts/<slug>.md → queue/<slug>.md (no rename, preserves slug)."""
    QUEUE.mkdir(parents=True, exist_ok=True)
    dest = QUEUE / path.name
    if dest.exists():
        # Defensive: don't clobber existing queue items.
        raise FileExistsError(f"queue file already exists: {dest}")
    shutil.move(str(path), str(dest))
    return dest


def write_report(grades: list[Grade]) -> None:
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "threshold_promote": DEFAULT_THRESHOLD,
        "threshold_review": REVIEW_THRESHOLD,
        "counts": {
            "total": len(grades),
            "promoted": sum(1 for g in grades if g.action == "promote"),
            "review": sum(1 for g in grades if g.action == "review"),
            "discard_flag": sum(1 for g in grades if g.action == "discard_flag"),
        },
        "grades": [asdict(g) for g in grades],
    }
    REPORT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--dry-run", action="store_true",
                   help="Skip API calls; use heuristic scoring. Safe without ANTHROPIC_API_KEY.")
    p.add_argument("--threshold", type=int, default=DEFAULT_THRESHOLD,
                   help=f"Min score for auto-promotion. Default: {DEFAULT_THRESHOLD}.")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    model = os.environ.get("ANTHROPIC_MODEL", DEFAULT_MODEL)

    if not DRAFTS.exists():
        print("⚠️  drafts/ dir missing — nothing to grade.")
        return 0
    drafts = sorted([p for p in DRAFTS.glob("*.md") if p.name.lower() != "readme.md"])
    if not drafts:
        print("✅ No drafts to grade.")
        write_report([])
        return 0

    print(f"🎓 Grading {len(drafts)} draft(s) (threshold: {args.threshold}, "
          f"model: {model}, dry-run: {args.dry_run})")

    grades: list[Grade] = []
    for path in drafts:
        print(f"\n   📝 {path.name}")
        g = grade_one(path, model=model, dry_run=args.dry_run)
        print(f"      score: {g.score}/100  → {g.action}")
        if g.scores:
            print("      breakdown: " + "  ".join(f"{k}={v}" for k, v in g.scores.items()))
        if g.reasoning:
            print(f"      reasoning: {g.reasoning[:160]}")
        if g.action == "promote" and not args.dry_run:
            try:
                dest = promote(path)
                g.promoted_to = str(dest.relative_to(REPO))
                print(f"      ✅ promoted → {g.promoted_to}")
            except Exception as e:
                print(f"      ❌ promotion failed: {e}", file=sys.stderr)
                g.action = "review"
        grades.append(g)

    write_report(grades)

    counts = {
        "promoted": sum(1 for g in grades if g.action == "promote"),
        "review":   sum(1 for g in grades if g.action == "review"),
        "discard":  sum(1 for g in grades if g.action == "discard_flag"),
    }
    print(f"\n📊 Results: {counts['promoted']} promoted, {counts['review']} review, "
          f"{counts['discard']} discard-flagged")
    print(f"📄 Report: {REPORT.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
