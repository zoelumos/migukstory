"""Shared configuration and tool discovery for the Migukstory YouTube pipeline.

The pipeline turns an already-published Migukstory article into a vertical
Korean-narrated "설명형" news Short. It is intentionally free-tier friendly:

  Chromium (headless slides)  +  edge-tts (free Korean voice)  +  ffmpeg
  +  YouTube Data API v3 (OAuth refresh token)

Every heavy binary is auto-discovered so the same code runs both in this
repo's CI (GitHub Actions installs system ffmpeg/chromium/fonts) and on a
developer box (imageio-ffmpeg + Playwright's bundled Chromium).
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

# ── Repo layout ────────────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parents[2]
BLOG_DIR = REPO_ROOT / "src" / "content" / "blog"
# Video build artifacts live outside git (see .gitignore rule added for this dir).
BUILD_DIR = REPO_ROOT / "build" / "youtube"

SITE_URL = os.environ.get("SITE_URL", "https://migukstory.com")

# ── Canvas ─────────────────────────────────────────────────────────────────
# 1080x1920 vertical = YouTube Shorts / Reels / TikTok native.
WIDTH = 1080
HEIGHT = 1920
FPS = 30

# ── Korean voices (edge-tts, free) ─────────────────────────────────────────
# SunHi = warm female news read; InJoon = authoritative male. Both ko-KR.
VOICE_DEFAULT = os.environ.get("YT_TTS_VOICE", "ko-KR-SunHiNeural")
VOICE_ALT = "ko-KR-InJoonNeural"
# edge-tts rate: slightly faster reads better for punchy Shorts pacing.
TTS_RATE = os.environ.get("YT_TTS_RATE", "+8%")

# ── Category → brand color + on-screen badge (mirrors src/content.config.ts) ─
CATEGORY_META = {
    "immigration": {"label": "이민·비자", "color": "#B91C1C"},
    "tax": {"label": "세금·재테크", "color": "#1E40AF"},
    "economy": {"label": "경제·산업", "color": "#0F766E"},
    "ai": {"label": "AI·자동화", "color": "#6D28D9"},
    "robotics": {"label": "로봇·미래직업", "color": "#C2410C"},
    "health": {"label": "건강·보험", "color": "#047857"},
}
DEFAULT_CATEGORY_META = {"label": "미국생활", "color": "#0f172a"}


def category_meta(category: str) -> dict:
    return CATEGORY_META.get((category or "").strip(), DEFAULT_CATEGORY_META)


# ── Binary discovery ───────────────────────────────────────────────────────
def find_ffmpeg() -> str:
    """Locate a *full-featured* ffmpeg (needs lavfi/drawtext).

    Order: $FFMPEG_BIN → PATH → imageio-ffmpeg's bundled static build.
    Note: Playwright's bundled ffmpeg is a stripped screen-recorder build
    without lavfi, so it is intentionally NOT used here.
    """
    env = os.environ.get("FFMPEG_BIN")
    if env and Path(env).exists():
        return env
    on_path = shutil.which("ffmpeg")
    if on_path:
        return on_path
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(
            "No ffmpeg found. Install system ffmpeg or `pip install imageio-ffmpeg`."
        ) from exc


def find_chromium() -> str:
    """Locate a Chromium/Chrome binary for headless slide rendering."""
    env = os.environ.get("CHROMIUM_BIN")
    if env and Path(env).exists():
        return env
    for name in ("chromium", "chromium-browser", "google-chrome", "chrome"):
        found = shutil.which(name)
        if found:
            return found
    # Playwright's bundled Chromium (present in this repo's CI image).
    pw_root = Path(os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "/opt/pw-browsers"))
    if pw_root.exists():
        candidates = sorted(pw_root.glob("chromium*/chrome-linux/chrome"))
        if candidates:
            return str(candidates[-1])
    raise RuntimeError(
        "No Chromium found. Set CHROMIUM_BIN or install chromium / Playwright."
    )
