"""Monetization-safety gate for generated video scripts.

Adapted from the community-validated "niche intelligence" pattern in Verticals
v3 (rushindrasinha/youtube-shorts-pipeline, ⭐2.1k), whose per-niche
`forbidden_phrases` block keeps finance/legal content inside YouTube's
monetization rules. Migukstory's lanes are *sensitive* topics — immigration
(legal), tax (finance), health (medical) — exactly the categories YouTube's
2026 "inauthentic content" update scrutinizes most, so a compliance pass
before publish is a hard monetization requirement, not a nicety.

The gate flags:
  1. Forbidden claims (guarantees, "financial/legal advice", get-rich-quick).
  2. Missing professional-consultation disclaimer on legal/medical/tax topics.
  3. Verbatim-reading risk (narration nearly identical to the source article),
     which YouTube treats as low-value "inauthentic" content.

It never rewrites silently — it reports, so a human keeps the creative call.
"""

from __future__ import annotations

import re

# Claims that trigger demonetization / policy strikes if voiced as fact.
# Korean + English, matched case-insensitively.
FORBIDDEN_GLOBAL = [
    "무조건 승인", "100% 승인", "100퍼센트", "확실히 통과", "반드시 통과",
    "보장", "보장합니다", "보장된", "guaranteed",
    "떼돈", "일확천금", "무조건 돈", "확정 수익", "확정 환급",
    "get rich", "quick money",
]
FORBIDDEN_BY_CATEGORY = {
    "immigration": ["변호사 없이도 확실", "무조건 영주권", "100% 비자", "합법적으로 우회"],
    "tax": ["세금 안 내는 법", "탈세", "무조건 환급", "확정 환급", "not financial advice but"],
    "health": ["무조건 완치", "부작용 없음", "의사 필요 없", "확실한 치료"],
    "economy": ["확정 수익", "무조건 오른다", "무조건 떨어진다", "베팅"],
}
# Topics that legally/ethically require a "consult a professional" disclaimer.
NEEDS_DISCLAIMER = {"immigration", "tax", "health"}
DISCLAIMER_HINTS = ["상담", "전문가", "변호사", "세무", "의사", "일반 정보", "참고"]


def _find(patterns: list[str], text: str) -> list[str]:
    low = text.lower()
    return [p for p in patterns if p.lower() in low]


def check_compliance(script: dict, source_body: str | None = None) -> dict:
    """Return {ok, violations[], warnings[]} for a built video script."""
    category = (script.get("category") or "").strip()
    narration = " ".join(s.get("narration", "") for s in script.get("scenes", []))
    on_screen = " ".join(
        " ".join(s.get("bullets", []))
        + " ".join(" ".join(r) for r in s.get("rows", []))
        + " ".join(s.get("steps", []))
        for s in script.get("scenes", [])
    )
    full = f"{narration} {on_screen} {script.get('video',{}).get('description','')}"

    violations: list[str] = []
    warnings: list[str] = []

    # 1) Forbidden claims.
    for hit in _find(FORBIDDEN_GLOBAL, full):
        violations.append(f"금지 표현(전역): '{hit}' — 단정·보장성 표현은 수익화 위험")
    for hit in _find(FORBIDDEN_BY_CATEGORY.get(category, []), full):
        violations.append(f"금지 표현({category}): '{hit}'")

    # 2) Missing disclaimer on sensitive topics.
    if category in NEEDS_DISCLAIMER:
        if not any(h in full for h in DISCLAIMER_HINTS):
            warnings.append(
                f"{category}: 전문가 상담/일반정보 고지 문구가 없음 — 법률·세무·의료 "
                "주제는 '일반 정보이며 전문가 상담 권장' 고지를 CTA에 넣으세요."
            )

    # 3) Verbatim-reading risk vs the source article body.
    if source_body:
        warnings.extend(_verbatim_warnings(script, source_body))

    return {
        "ok": not violations,
        "category": category,
        "violations": violations,
        "warnings": warnings,
    }


def _verbatim_warnings(script: dict, source_body: str) -> list[str]:
    """Flag scenes whose narration is lifted near-verbatim from the article.

    YouTube's "inauthentic content" rule penalizes reading source text aloud
    unchanged; narration should transform (summarize/explain), not copy.
    """
    warns: list[str] = []
    src_sentences = {
        re.sub(r"\s+", "", s)[:40]
        for s in re.split(r"[.!?\n]", source_body) if len(s.strip()) > 20
    }
    for sc in script.get("scenes", []):
        narr = sc.get("narration", "")
        key = re.sub(r"\s+", "", narr)[:40]
        if key and key in src_sentences:
            warns.append(
                f"장면 '{sc.get('id')}': 나레이션이 기사 원문과 거의 동일 — "
                "요약·해설형으로 바꿔야 '비진정성' 위험을 피합니다."
            )
    return warns


def format_report(result: dict) -> str:
    lines = [f"── 수익화 컴플라이언스 체크 ({result['category'] or '일반'}) ──"]
    if result["ok"] and not result["warnings"]:
        lines.append("✅ 통과 — 금지 표현/고지 문제 없음.")
        return "\n".join(lines)
    for v in result["violations"]:
        lines.append(f"❌ {v}")
    for w in result["warnings"]:
        lines.append(f"⚠️  {w}")
    if result["ok"]:
        lines.append("→ 치명 위반 없음(경고만). 게시 가능하나 위 항목 검토 권장.")
    else:
        lines.append("→ ❌ 치명 위반 있음. 나레이션/문구 수정 후 재생성 권장.")
    return "\n".join(lines)


if __name__ == "__main__":
    import argparse
    import json
    from pathlib import Path

    ap = argparse.ArgumentParser(description="Monetization compliance gate")
    ap.add_argument("script", help="script.json from article_to_script")
    ap.add_argument("--source", help="Optional source article .md for verbatim check")
    args = ap.parse_args()

    script = json.loads(Path(args.script).read_text(encoding="utf-8"))
    body = Path(args.source).read_text(encoding="utf-8") if args.source else None
    result = check_compliance(script, body)
    print(format_report(result))
    raise SystemExit(0 if result["ok"] else 1)
