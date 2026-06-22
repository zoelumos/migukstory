#!/usr/bin/env python3
"""
Validate and improve AI RSS drafts before editorial grading.

This is the middle step in the daily pipeline:
  ingest -> validate/improve -> editorial grade/review

It reads the manifest written by draft_from_rss.py (or an explicit --only list),
checks each draft still exists under drafts/, and asks Claude Code CLI to improve
that draft using source-backed research/context. The goal is not to invent a new
article; it is to strengthen factual density, Korean-American impact analysis,
and source traceability before editor_grade.py scores the result.

Safety rules:
- Only rewrites files in drafts/.
- Preserves valid Markdown with YAML frontmatter.
- Requires a ## 출처 (Sources) section.
- Rejects outputs that lose sourceUrl/official source attribution.
- One slow/bad draft is skipped, not fatal to the whole cron.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
DRAFTS = REPO / "drafts"
DEFAULT_CLI_TIMEOUT = 180
DEFAULT_MODEL = "claude-opus-4-8"

SOURCE_URL_RE = re.compile(r"^sourceUrl:\s*['\"]?([^'\"\n]+)['\"]?\s*$", re.MULTILINE)
SOURCE_RE = re.compile(r"^source:\s*['\"]?([^'\"\n]+)['\"]?\s*$", re.MULTILINE)

SYSTEM_PROMPT = """You are the validation-and-improvement editor for migukstory.com,
a Korean-American community news site.

You improve ONE Korean draft at a time before final editorial grading.
Your job is to make the draft more publishable by strengthening:
1) factual traceability,
2) concrete Korean-American reader impact,
3) original editorial synthesis that follows logically from verified facts,
4) structure and clarity.

Hard rules:
- Output the full improved Markdown draft only. No preamble, no code fences.
- Keep YAML frontmatter. Keep draft: true unless already different.
- Do not invent facts. Every new concrete claim must be traceable to a source.
- Prefer official/primary/semi-primary sources: government, regulator, official statistics, court/agency docs, or major newsroom coverage.
- If you use an additional source, add it to ## 출처 (Sources) with its URL.
- Do not copy long passages. Paraphrase.
- Korean throughout except proper names/acronyms.
- Never give legal, tax, medical, immigration, or investment advice. Use cautious wording and recommend expert consultation where relevant.
"""

USER_PROMPT_TEMPLATE = """다음 초안을 검증하고 보강하세요.

목표:
- GSC 성과 기준 최신 편집 방향: USCIS/이민 글이 실제 Google impressions/clicks를 만들고 있으므로 이민/USCIS, 세금/IRS, 연금/Social Security, 주택/모기지, 보험/Medicare/ACA, 한인 생활가이드 각도를 최우선으로 보강하세요. 단, 경제와 AI/robotics는 계속 유지해야 하는 핵심 보조 카테고리입니다. 해당 초안이 경제·AI·로보틱스라면 한인 일자리, 자영업, 시장/은퇴계좌, 자동화 리스크, 자녀 진로와 연결해 실용적으로 살리세요.
- 원 출처 링크를 확인하고, 가능하면 같은 주제를 뒷받침하는 공식/신뢰 출처를 1~2개 더 찾아 비교하세요.
- 원문에 없는 사실을 만들지 말고, 확인 가능한 사실만 추가하세요.
- 미주 한인 독자에게 왜 중요한지 구체적으로 보강하세요. 한인 자영업자, 유학생, 취업비자/영주권자, 은퇴자, 부모 세대, 한인 가정 중 해당 그룹을 골라 실제 의사결정/서류/세금/건강/생활비/커뮤니티 영향으로 설명하세요.
- 단순 번역/요약이 아니라, 출처 기반 편집자 분석을 한 문단 이상 넣으세요.
- Migukstory의 차별점은 시각화입니다. 초안에 유용한 시각화가 없으면 반드시 `## 한눈에 보는 변화` 섹션을 추가하고, 기사 성격에 맞게 번호 매긴 단계별 체크리스트, 짧은 타임라인, 또는 Markdown 비교표 중 하나 이상을 넣으세요. Mermaid, flowchart/graph, sequenceDiagram, gantt 등 코드형 다이어그램은 사이트에서 깨질 수 있으므로 절대 넣지 마세요. 절차/자격/이민/혜택/정책 변경 글은 모바일에서 바로 읽히는 표/목록 시각화 없이는 불완전한 글로 봅니다.
- title/description도 보강된 내용에 맞게 개선해도 됩니다.

원 출처:
- source: {source_name}
- sourceUrl: {source_url}

현재 초안:
----- 초안 시작 -----
{draft}
----- 초안 끝 -----

반드시 전체 Markdown만 출력하세요.
"""


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    p.add_argument("--manifest", metavar="PATH", help="Manifest from draft_from_rss.py")
    p.add_argument("--only", nargs="*", help="Explicit draft paths to improve")
    p.add_argument("--dry-run", action="store_true", help="Plan only; no Claude calls or writes")
    p.add_argument("--max-drafts", type=int, default=24, help="Max drafts to improve")
    p.add_argument("--time-budget", type=int, default=0, help="Wall-clock budget seconds; 0 unlimited")
    p.add_argument("--cli-timeout", type=int, default=DEFAULT_CLI_TIMEOUT, help="Per Claude CLI timeout")
    return p.parse_args()


def manifest_paths(path: str | None) -> list[Path]:
    if not path:
        return []
    p = Path(path)
    if not p.exists():
        print(f"⚠️  manifest not found: {p}", file=sys.stderr)
        return []
    data = json.loads(p.read_text(encoding="utf-8"))
    out: list[Path] = []
    for raw in data.get("drafts", []):
        dp = Path(raw)
        if not dp.is_absolute():
            dp = REPO / dp
        out.append(dp)
    return out


def collect_targets(args: argparse.Namespace) -> list[Path]:
    paths: list[Path] = []
    if args.only:
        for raw in args.only:
            p = Path(raw)
            if not p.is_absolute():
                p = REPO / p
            paths.append(p)
    paths.extend(manifest_paths(args.manifest))

    seen: set[Path] = set()
    out: list[Path] = []
    for p in paths:
        try:
            rp = p.resolve()
        except FileNotFoundError:
            rp = p
        if rp in seen:
            continue
        seen.add(rp)
        if not p.exists():
            print(f"⚠️  skip missing draft: {p.relative_to(REPO) if p.is_absolute() and p.is_relative_to(REPO) else p}")
            continue
        if not p.resolve().is_relative_to(DRAFTS.resolve()):
            print(f"⚠️  skip non-drafts path: {p}", file=sys.stderr)
            continue
        out.append(p)
    return out[: max(1, args.max_drafts)]


def extract_meta(md: str) -> tuple[str, str]:
    source_url = ""
    source_name = ""
    m = SOURCE_URL_RE.search(md)
    if m:
        source_url = m.group(1).strip()
    m = SOURCE_RE.search(md)
    if m:
        source_name = m.group(1).strip()
    return source_name or "(source missing)", source_url or "(sourceUrl missing)"


def call_claude(path: Path, md: str, cli_timeout: int, model: str | None = None) -> str:
    source_name, source_url = extract_meta(md)
    model = model or os.environ.get("ANTHROPIC_MODEL", DEFAULT_MODEL)
    prompt = SYSTEM_PROMPT + "\n\n" + USER_PROMPT_TEMPLATE.format(
        source_name=source_name,
        source_url=source_url,
        draft=md,
    )
    cmd = [
        "claude", "-p", prompt,
        "--model", model,
        "--output-format", "text",
        "--max-turns", "8",
        "--allowedTools", "WebFetch,WebSearch",
    ]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            timeout=cli_timeout,
            stdin=subprocess.DEVNULL,
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"claude -p timed out ({cli_timeout}s)")
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"claude -p failed ({e.returncode}): {(e.stderr or '')[:500]}")
    except FileNotFoundError:
        sys.exit("❌ `claude` CLI not found in PATH")
    return result.stdout.strip()


def valid_improved(md: str, original: str) -> tuple[bool, str]:
    if not md.startswith("---"):
        return False, "missing YAML frontmatter"
    if md.count("---") < 2:
        return False, "frontmatter not closed"
    if "## 출처" not in md and "출처 (Sources)" not in md:
        return False, "missing sources section"
    _, original_url = extract_meta(original)
    if original_url and original_url != "(sourceUrl missing)" and original_url not in md:
        return False, "lost original sourceUrl"
    if len(md) < max(800, len(original) * 0.75):
        return False, "output suspiciously short"
    return True, ""


def write_manifest_update(path: str | None, improved: list[Path]) -> None:
    if not path:
        return
    p = Path(path)
    if not p.exists():
        return
    try:
        data: dict[str, Any] = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return
    data["improved_at"] = datetime.now(timezone.utc).isoformat()
    data["improved_drafts"] = [str(x.relative_to(REPO)) for x in improved]
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    targets = collect_targets(args)
    if not targets:
        print("✅ No draft files to improve.")
        return 0

    print(f"🔎 Validate/improve {len(targets)} draft(s) (dry-run: {args.dry_run})")
    for p in targets:
        print(f"   - {p.relative_to(REPO)}")

    if args.dry_run:
        return 0

    start = time.monotonic()
    improved: list[Path] = []
    skipped: list[tuple[Path, str]] = []

    for idx, p in enumerate(targets):
        if args.time_budget and (time.monotonic() - start) > args.time_budget:
            skipped.extend((x, "time budget exhausted") for x in targets[idx:])
            print(f"⏱  Time budget exhausted; deferring {len(targets) - idx} draft(s)")
            break

        original = p.read_text(encoding="utf-8")
        print(f"\n🛠️  Improving: {p.name}")
        try:
            new_md = call_claude(p, original, args.cli_timeout, os.environ.get("ANTHROPIC_MODEL", DEFAULT_MODEL))
            ok, reason = valid_improved(new_md, original)
            if not ok:
                raise RuntimeError(reason)
        except Exception as e:
            print(f"   ⚠️  skipped: {e}")
            skipped.append((p, str(e)))
            continue

        if new_md.rstrip() == original.rstrip():
            print("   = no change")
            continue
        p.write_text(new_md.rstrip() + "\n", encoding="utf-8")
        improved.append(p)
        print(f"   ✅ improved {p.relative_to(REPO)}")

    write_manifest_update(args.manifest, improved)
    print(f"\n📊 Improved {len(improved)} draft(s); skipped {len(skipped)}.")
    for p, reason in skipped:
        print(f"   ! {p.relative_to(REPO)} — {reason}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
