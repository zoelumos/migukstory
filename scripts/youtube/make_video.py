"""End-to-end: a published article slug → a YouTube-ready Short (+ optional upload).

    article (.md)
      → article_to_script   (Korean script + scene breakdown)
      → render_slides        (Chromium → 1080x1920 PNGs)
      → synth_tts            (edge-tts Korean narration)
      → assemble_video       (ffmpeg → vertical MP4)
      → upload_youtube       (Data API v3, optional)

This is the single entry point the GitHub Actions workflow calls. It is fully
automated (no prompts) in line with the repo's prime directive.

Usage:
    python -m scripts.youtube.make_video <slug> [--upload] [--privacy unlisted]
                                          [--claude] [--allow-silent-fallback]
    python -m scripts.youtube.make_video --latest        # newest published post
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__:
    from .config import BUILD_DIR, BLOG_DIR
    from . import article_to_script, render_slides, synth_tts, assemble_video
else:  # pragma: no cover
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from config import BUILD_DIR, BLOG_DIR  # type: ignore
    import article_to_script, render_slides, synth_tts, assemble_video  # type: ignore


def _latest_slug() -> str:
    """Newest *published* post by frontmatter pubDate.

    mtime is unreliable in CI (a fresh checkout stamps every file with the same
    time), so rank by the pubDate declared in the article itself.
    """
    import re

    best_slug, best_key = None, ""
    for p in BLOG_DIR.glob("*.md"):
        text = p.read_text(encoding="utf-8", errors="ignore")[:800]
        if re.search(r"^draft:\s*true", text, re.MULTILINE):
            continue
        m = re.search(r"^pubDate:\s*['\"]?(\d{4}-\d{2}-\d{2})", text, re.MULTILINE)
        key = (m.group(1) if m else "0000-00-00") + "|" + p.stem
        if key > best_key:
            best_key, best_slug = key, p.stem
    if not best_slug:
        raise SystemExit(f"No published articles in {BLOG_DIR}")
    return best_slug


def make(slug: str, *, upload: bool = False, privacy: str | None = None,
         use_claude: bool = False, allow_silent: bool = False,
         music: Path | None = None) -> dict:
    print(f"\n━━ Building Short for: {slug} ━━")
    workdir = BUILD_DIR / slug
    workdir.mkdir(parents=True, exist_ok=True)
    script_path = workdir / "script.json"

    print("① Article → script")
    script = article_to_script.build_script(slug)
    if use_claude:
        script = article_to_script.enhance_with_claude(script)
    script_path.write_text(json.dumps(script, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"   {len(script['scenes'])} scenes | category={script['category']}")

    print("② Rendering slides")
    render_slides.render_slides(script, workdir / "slides")

    print("③ Synthesizing narration")
    synth_tts.synth(script, workdir / "audio", allow_silent=allow_silent)

    print("④ Assembling video")
    out_mp4 = workdir / f"{slug}.mp4"
    assemble_video.assemble(script, out_mp4, music=music)

    script_path.write_text(json.dumps(script, ensure_ascii=False, indent=2), encoding="utf-8")

    result = {
        "slug": slug,
        "video_file": str(out_mp4),
        "duration": script["video"].get("duration"),
        "title": script["video"]["title"],
        "tts_fallback": script.get("_tts_fallback", False),
        "youtube_url": None,
    }

    if upload:
        print("⑤ Uploading to YouTube")
        if __package__:
            from . import upload_youtube
        else:  # pragma: no cover
            import upload_youtube  # type: ignore
        result["youtube_url"] = upload_youtube.upload(out_mp4, script["video"], privacy=privacy)

    print(f"\n✅ Done: {out_mp4}")
    if result["tts_fallback"]:
        print("   ⚠ narration was SILENT fallback (TTS endpoint unreachable here).")
    return result


def main() -> None:
    ap = argparse.ArgumentParser(description="Article → YouTube Short (end to end)")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("slug", nargs="?", help="Blog slug / partial / path")
    g.add_argument("--latest", action="store_true", help="Use newest published post")
    ap.add_argument("--upload", action="store_true", help="Upload to YouTube when done")
    ap.add_argument("--privacy", choices=["private", "unlisted", "public"],
                    help="Override upload privacy (default: private)")
    ap.add_argument("--claude", action="store_true", help="Polish narration via Claude if key set")
    ap.add_argument("--allow-silent-fallback", action="store_true",
                    help="Silent audio if TTS endpoint is blocked (sandboxes)")
    ap.add_argument("--music", help="Optional bed music file")
    args = ap.parse_args()

    slug = _latest_slug() if args.latest else args.slug
    result = make(
        slug, upload=args.upload, privacy=args.privacy, use_claude=args.claude,
        allow_silent=args.allow_silent_fallback,
        music=Path(args.music) if args.music else None,
    )

    import os
    gh_out = os.environ.get("GITHUB_OUTPUT")
    if gh_out:
        with open(gh_out, "a", encoding="utf-8") as fh:
            fh.write(f"video_file={result['video_file']}\n")
            fh.write(f"youtube_url={result.get('youtube_url') or ''}\n")
            fh.write(f"tts_fallback={str(result['tts_fallback']).lower()}\n")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
