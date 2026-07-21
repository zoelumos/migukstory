"""Convert a published Migukstory article (Markdown) into a video script.

The output is a plain-dict "VideoScript" that downstream stages
(render_slides → synth_tts → assemble_video) consume. It is deterministic and
offline by default — every scene is extracted from the article's own
frontmatter and body — because Migukstory articles are already written
"visualization-first" (핵심 요약 bullets, comparison tables, numbered steps),
which maps almost 1:1 onto Short scenes.

An optional Claude pass (`enhance_with_claude`, gated on ANTHROPIC_API_KEY)
can rewrite the spoken narration for punchier pacing without changing the
on-screen facts. It is off unless a key is present, so the base pipeline stays
free and reproducible.

Usage:
    python -m scripts.youtube.article_to_script <slug-or-path> [--out script.json]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.exit("PyYAML required: pip install pyyaml")

# Support both `python -m scripts.youtube.article_to_script` and direct run.
if __package__:
    from .config import BLOG_DIR, SITE_URL, category_meta
else:  # pragma: no cover
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from config import BLOG_DIR, SITE_URL, category_meta  # type: ignore

FM_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
# Scenes beyond this make a Short too long; we keep the strongest.
MAX_CONTENT_SCENES = 5
MAX_TABLE_ROWS = 4  # Shorts: >4 rows overflows the vertical canvas.
MAX_BULLETS = 4


# ── Article parsing ────────────────────────────────────────────────────────
def load_article(slug_or_path: str) -> tuple[dict, str, Path]:
    """Return (frontmatter, body, path) for a slug or explicit .md path."""
    path = Path(slug_or_path)
    if not path.exists():
        cand = BLOG_DIR / f"{slug_or_path}.md"
        if cand.exists():
            path = cand
        else:
            matches = sorted(BLOG_DIR.glob(f"*{slug_or_path}*.md"))
            if not matches:
                raise FileNotFoundError(f"No article for '{slug_or_path}'")
            path = matches[0]
    raw = path.read_text(encoding="utf-8")
    m = FM_RE.match(raw)
    if not m:
        raise ValueError(f"{path} has no YAML frontmatter")
    fm = yaml.safe_load(m.group(1)) or {}
    body = raw[m.end():]
    return fm, body, path


def _strip_md(text: str) -> str:
    """Flatten inline markdown to clean prose for narration/captions."""
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)  # links → label
    text = re.sub(r"[*_`]+", "", text)                     # emphasis/code
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?。])\s+|(?<=니다)\s+|(?<=세요)\s+", text.strip())
    return [p.strip() for p in parts if p.strip()]


def _split_sections(body: str) -> list[tuple[str, str]]:
    """Split body into (heading, section_text) pairs at ## / ### headings."""
    sections: list[tuple[str, str]] = []
    current_head = ""
    buf: list[str] = []
    for line in body.splitlines():
        hm = re.match(r"^#{2,3}\s+(.*)", line)
        if hm:
            if buf:
                sections.append((current_head, "\n".join(buf).strip()))
            current_head = _strip_md(hm.group(1))
            buf = []
        else:
            buf.append(line)
    if buf:
        sections.append((current_head, "\n".join(buf).strip()))
    return sections


def _extract_bullets(section_text: str) -> list[str]:
    bullets = []
    for line in section_text.splitlines():
        bm = re.match(r"^\s*[-*]\s+(.*)", line)
        if bm:
            bullets.append(_strip_md(bm.group(1)))
    return bullets


def _extract_numbered(section_text: str) -> list[str]:
    steps = []
    for line in section_text.splitlines():
        nm = re.match(r"^\s*\d+\.\s+(.*)", line)
        if nm:
            steps.append(_strip_md(nm.group(1)))
    return steps


def _extract_tables(body: str) -> list[dict]:
    """Return markdown tables as {headers, rows, title} dicts, richest first.

    `title` is the nearest preceding ## / ### heading, so a table scene's
    caption always matches the table it actually shows.
    """
    tables = []
    lines = body.splitlines()
    current_head = ""
    i = 0
    while i < len(lines):
        line = lines[i]
        hm = re.match(r"^#{2,3}\s+(.*)", line)
        if hm:
            current_head = _strip_md(hm.group(1))
            i += 1
            continue
        if "|" in line and i + 1 < len(lines) and re.match(r"^\s*\|?[\s:|-]+\|", lines[i + 1]):
            headers = [_strip_md(c) for c in line.strip().strip("|").split("|")]
            rows = []
            j = i + 2
            while j < len(lines) and "|" in lines[j]:
                cells = [_strip_md(c) for c in lines[j].strip().strip("|").split("|")]
                if any(cells):
                    rows.append(cells)
                j += 1
            if rows:
                tables.append({"headers": headers, "rows": rows, "title": current_head})
            i = j
        else:
            i += 1
    tables.sort(key=lambda t: len(t["rows"]), reverse=True)
    return tables


# ── Narration helpers ──────────────────────────────────────────────────────
def _clean_headline(title: str) -> tuple[str, str]:
    """Split a Migukstory headline on its em dash into (main, kicker)."""
    for sep in (" — ", " – ", " - "):
        if sep in title:
            a, b = title.split(sep, 1)
            return a.strip(), b.strip()
    return title.strip(), ""


def _josa(word: str, pair: str = "은는") -> str:
    """Append the correct Korean particle for `word`.

    pair[0] follows a final consonant (받침), pair[1] follows a vowel.
    Handles 은/는, 이/가, 을/를, 과/와.
    """
    word = word.strip()
    if not word:
        return word
    ch = word[-1]
    if "가" <= ch <= "힣":
        has_batchim = (ord(ch) - 0xAC00) % 28 != 0
        return word + (pair[0] if has_batchim else pair[1])
    # Non-Hangul tail (digit/latin): default to the consonant form.
    return word + pair[0]


def _first_meaningful(bullets: list[str], n: int) -> list[str]:
    seen, out = set(), []
    for b in bullets:
        key = b[:24]
        if key in seen:
            continue
        seen.add(key)
        out.append(b)
        if len(out) >= n:
            break
    return out


# ── Script construction ────────────────────────────────────────────────────
def build_script(slug_or_path: str) -> dict:
    fm, body, path = load_article(slug_or_path)
    slug = path.stem
    category = fm.get("category", "")
    meta = category_meta(category)
    title = str(fm.get("title", slug))
    description = _strip_md(str(fm.get("description", "")))
    main, kicker = _clean_headline(title)

    sections = _split_sections(body)
    tables = _extract_tables(body)

    scenes: list[dict] = []

    # 1) Hook — the headline + the single most urgent fact.
    hook_line = _sentences(description)
    scenes.append({
        "id": "hook",
        "kind": "hook",
        "badge": meta["label"],
        "headline": main,
        "sub": kicker or (hook_line[0] if hook_line else ""),
        "narration": _hook_narration(main, kicker, hook_line),
        "min_display": 4.0,
    })

    # 2) 핵심 요약 — prefer an explicit summary section, else the description.
    summary_bullets: list[str] = []
    for head, text in sections:
        if any(k in head for k in ("핵심 요약", "핵심요약", "요약", "한눈에")):
            summary_bullets = _extract_bullets(text)
            break
    if not summary_bullets:
        summary_bullets = _sentences(description)
    summary_bullets = _first_meaningful(summary_bullets, MAX_BULLETS)
    if summary_bullets:
        scenes.append({
            "id": "summary",
            "kind": "points",
            "title": "핵심 요약",
            "bullets": summary_bullets,
            # Spoken line is a short hook; the bullets are read on-screen.
            "narration": "먼저 핵심만 짚어드릴게요. " + _sentences(summary_bullets[0])[0],
            "min_display": 6.0,
        })

    # 3) Best comparison table (the visual product differentiator).
    if tables:
        t = tables[0]
        rows = t["rows"][:MAX_TABLE_ROWS]
        table_title = t.get("title") or "한눈에 비교"
        scenes.append({
            "id": "table",
            "kind": "table",
            "title": table_title,
            "headers": t["headers"],
            "rows": rows,
            "narration": _table_narration(table_title, rows),
            "min_display": 7.5,
        })

    # 4) Steps / checklist — a numbered process if the article has one.
    steps_scene = _find_steps_scene(sections)
    if steps_scene:
        scenes.append(steps_scene)

    # 5) If we still have room and there is a second, *distinct* strong table.
    if len(scenes) < 2 + MAX_CONTENT_SCENES and len(tables) > 1:
        t2 = tables[1]
        if t2.get("title") and t2["title"] != tables[0].get("title"):
            scenes.append({
                "id": "table2",
                "kind": "table",
                "title": t2["title"],
                "headers": t2["headers"],
                "rows": t2["rows"][:MAX_TABLE_ROWS],
                "narration": _table_narration(t2["title"], t2["rows"]),
                "min_display": 7.5,
            })

    # 6) CTA — always last. Sensitive lanes (immigration/tax/health) append a
    # "general info, consult a professional" disclaimer — a YouTube
    # monetization requirement for legal/medical/financial topics.
    url = f"{SITE_URL}/blog/{slug}/"
    cta_narration = "자세한 내용과 출처는 미국스토리 닷컴에서 확인하세요. 구독하고 최신 소식 받아보세요."
    if category in ("immigration", "tax", "health"):
        cta_narration += " 이 영상은 일반 정보이며, 개인 상황은 전문가 상담을 권장합니다."
    scenes.append({
        "id": "cta",
        "kind": "cta",
        "headline": "전체 내용은",
        "sub": "migukstory.com",
        "narration": cta_narration,
        "min_display": 4.5,
    })

    return {
        "slug": slug,
        "source_file": str(path.relative_to(path.parents[3])) if len(path.parents) >= 4 else str(path),
        "category": category,
        "color": meta["color"],
        "badge": meta["label"],
        "video": _youtube_metadata(fm, slug, url),
        "scenes": scenes,
    }


def _hook_narration(main: str, kicker: str, hook_line: list[str]) -> str:
    lead = main.rstrip("!?.")
    if kicker:
        return f"{lead}. {kicker}. 한인이라면 지금 꼭 확인하세요."
    tail = hook_line[0] if hook_line else "지금 확인하세요."
    return f"{lead}. {tail}"


def _table_narration(title: str, rows: list[list[str]]) -> str:
    """Short spoken hook — viewers read the table on-screen for detail."""
    title = (title or "").strip()
    if title:
        return f"{title}. 핵심 차이를 표로 정리했어요. 화면에서 꼭 확인하세요."
    return "핵심 차이를 표로 정리했어요. 화면에서 확인하세요."


def _find_steps_scene(sections: list[tuple[str, str]]) -> dict | None:
    best: list[str] = []
    best_head = "단계별 절차"
    for head, text in sections:
        steps = _extract_numbered(text)
        checklist = _extract_bullets(text) if any(
            k in head for k in ("체크리스트", "확인", "해야", "준비")
        ) else []
        cand = steps or checklist
        if len(cand) > len(best):
            best = cand
            best_head = head or best_head
    if len(best) < 2:
        return None
    best = _first_meaningful(best, 4)
    return {
        "id": "steps",
        "kind": "steps",
        "title": best_head,
        "steps": best,
        # Spoken: name the process + count; steps are read on-screen.
        "narration": f"{_josa(best_head, '은는')} 순서대로 {len(best)}단계예요. 하나씩 볼게요.",
        "min_display": 8.0,
    }


def _youtube_metadata(fm: dict, slug: str, url: str) -> dict:
    title = str(fm.get("title", slug))
    # YouTube titles cap at 100 chars; keep the hook, drop the kicker if needed.
    yt_title = title
    if len(yt_title) > 95:
        main, _ = _clean_headline(title)
        yt_title = main[:95]
    yt_title = (yt_title + " #Shorts")[:100]

    tags = fm.get("tags", []) or []
    base_tags = ["미국이민", "한인", "미국생활", "재미교포", "migukstory"]
    all_tags = list(dict.fromkeys([*(str(t) for t in tags), *base_tags]))

    desc = _strip_md(str(fm.get("description", "")))
    body_desc = (
        f"{desc}\n\n"
        f"📄 전체 기사 보기: {url}\n"
        f"🔔 미국 한인 생활정보 — 이민·세금·건강보험·경제를 시각화해서 쉽게 전해드립니다.\n\n"
        f"#미국이민 #한인 #{fm.get('category','미국생활')} #Shorts"
    )
    return {
        "title": yt_title,
        "description": body_desc[:4900],
        "tags": all_tags[:15],
        "categoryId": "25",  # News & Politics
        "privacyStatus": "private",  # safe default; workflow can override
        "format": "shorts",
        "url": url,
    }


# ── Optional Claude narration polish (off unless ANTHROPIC_API_KEY set) ─────
def enhance_with_claude(script: dict) -> dict:
    """Rewrite each scene's narration for tighter Shorts pacing.

    Facts on the slides are never changed — only the spoken lines. No-op (and
    prints a note) when ANTHROPIC_API_KEY is absent or the SDK is missing, so
    the base pipeline stays free and deterministic.
    """
    import os

    if not os.environ.get("ANTHROPIC_API_KEY"):
        return script
    try:
        import anthropic
    except ImportError:
        print("[claude] anthropic SDK not installed; keeping deterministic narration")
        return script

    client = anthropic.Anthropic()
    scenes_for_prompt = [
        {"id": s["id"], "kind": s["kind"], "narration": s.get("narration", "")}
        for s in script["scenes"]
    ]
    prompt = (
        "너는 한인 대상 뉴스 쇼츠 성우 대본 작가다. 아래 각 장면의 나레이션을 "
        "구어체로, 한 장면당 1~2문장, 총 45~60초 분량으로 다듬어라. 사실은 바꾸지 말고 "
        "말맛만 살려라. JSON 배열 [{id, narration}] 형식으로만 답하라.\n\n"
        + json.dumps(scenes_for_prompt, ensure_ascii=False)
    )
    try:
        resp = client.messages.create(
            model=os.environ.get("YT_CLAUDE_MODEL", "claude-sonnet-5"),
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}],
        )
        text = resp.content[0].text
        text = re.search(r"\[.*\]", text, re.DOTALL).group(0)
        rewritten = {d["id"]: d["narration"] for d in json.loads(text)}
        for s in script["scenes"]:
            if s["id"] in rewritten and rewritten[s["id"]].strip():
                s["narration"] = rewritten[s["id"]].strip()
        print("[claude] narration polished")
    except Exception as exc:  # pragma: no cover
        print(f"[claude] polish skipped ({exc}); using deterministic narration")
    return script


def main() -> None:
    ap = argparse.ArgumentParser(description="Article Markdown → video script JSON")
    ap.add_argument("slug", help="Blog slug, partial match, or path to .md")
    ap.add_argument("--out", help="Write JSON here (default: stdout)")
    ap.add_argument("--claude", action="store_true", help="Polish narration with Claude if key present")
    args = ap.parse_args()

    script = build_script(args.slug)
    if args.claude:
        script = enhance_with_claude(script)

    out = json.dumps(script, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).write_text(out, encoding="utf-8")
        print(f"Wrote {args.out} ({len(script['scenes'])} scenes)")
    else:
        print(out)


if __name__ == "__main__":
    main()
