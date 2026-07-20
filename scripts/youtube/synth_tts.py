"""Synthesize Korean narration for each scene with edge-tts (free).

edge-tts streams from Microsoft's Edge read-aloud endpoint — no API key, good
ko-KR voices (SunHi / InJoon). It runs fine on GitHub Actions. In sandboxes
whose egress policy blocks speech.platform.bing.com, pass --allow-silent-
fallback to emit a silent track of the estimated read length so the rest of
the pipeline (timing, assembly) still produces a complete video.

Usage:
    python -m scripts.youtube.synth_tts script.json --outdir build/youtube/<slug>/audio
"""

from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
import sys
from pathlib import Path

if __package__:
    from .config import TTS_RATE, VOICE_DEFAULT, find_ffmpeg
else:  # pragma: no cover
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from config import TTS_RATE, VOICE_DEFAULT, find_ffmpeg  # type: ignore

# Average Korean narration pace at edge-tts +8% rate ≈ 7.5 chars/sec. Used only
# for the silent fallback and as a floor so short scenes still breathe.
CHARS_PER_SEC = 7.5
MIN_SCENE_SEC = 2.2


def _ensure_certifi_trusts_proxy() -> None:
    """Append the agent-proxy CA to certifi so aiohttp's TLS trusts the MITM.

    No-op outside the sandbox (bundle absent) and idempotent. Without this,
    edge-tts fails cert verification behind the Claude Code egress proxy.
    """
    ca = Path("/root/.ccr/ca-bundle.crt")
    if not ca.exists():
        return
    try:
        import certifi

        bundle = Path(certifi.where())
        text = bundle.read_text(encoding="utf-8", errors="ignore")
        if "AGENT PROXY CA" not in text:
            bundle.write_text(
                text + "\n# AGENT PROXY CA\n" + ca.read_text(encoding="utf-8"),
                encoding="utf-8",
            )
    except Exception:
        pass


def probe_duration(path: Path) -> float:
    """Return audio duration in seconds via ffmpeg (parses stderr)."""
    ff = find_ffmpeg()
    res = subprocess.run(
        [ff, "-hide_banner", "-i", str(path)], capture_output=True, text=True
    )
    for line in res.stderr.splitlines():
        if "Duration:" in line:
            hms = line.split("Duration:")[1].split(",")[0].strip()
            try:
                h, m, s = hms.split(":")
                return int(h) * 3600 + int(m) * 60 + float(s)
            except ValueError:
                break
    return 0.0


def _estimate_seconds(text: str) -> float:
    return max(MIN_SCENE_SEC, round(len(text) / CHARS_PER_SEC + 0.6, 2))


def _silent_track(out: Path, seconds: float) -> None:
    ff = find_ffmpeg()
    subprocess.run(
        [ff, "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi",
         "-i", "anullsrc=r=24000:cl=mono", "-t", f"{seconds:.2f}",
         "-c:a", "libmp3lame", "-q:a", "6", str(out)],
        check=True,
    )


async def _edge_tts(text: str, voice: str, out: Path) -> None:
    import edge_tts

    communicate = edge_tts.Communicate(text, voice, rate=TTS_RATE)
    await communicate.save(str(out))


def synth(script: dict, outdir: Path, allow_silent: bool = False,
          voice: str | None = None) -> list[dict]:
    outdir.mkdir(parents=True, exist_ok=True)
    _ensure_certifi_trusts_proxy()
    voice = voice or VOICE_DEFAULT
    tracks: list[dict] = []
    used_fallback = False

    for i, scene in enumerate(script["scenes"]):
        text = (scene.get("narration") or "").strip()
        out = outdir / f"audio_{i:02d}_{scene['id']}.mp3"
        made = False
        if text:
            try:
                asyncio.run(_edge_tts(text, voice, out))
                made = out.exists() and out.stat().st_size > 0
            except Exception as exc:
                if not allow_silent:
                    raise RuntimeError(
                        f"edge-tts failed on scene {i} ({scene['id']}): {exc}\n"
                        "Pass --allow-silent-fallback to build a timed silent "
                        "track instead (e.g. in an egress-restricted sandbox)."
                    ) from exc
                print(f"  scene {i:02d}: TTS blocked ({type(exc).__name__}); silent fallback")
        if not made:
            used_fallback = True
            _silent_track(out, _estimate_seconds(text or "무음"))

        dur = probe_duration(out) or _estimate_seconds(text or "무음")
        scene["audio"] = str(out)
        scene["duration"] = round(dur, 2)
        tracks.append({"id": scene["id"], "audio": str(out), "duration": scene["duration"]})
        tag = "silent" if (used_fallback and not made) else "voice"
        print(f"  audio {i:02d} [{tag:6}] {scene['duration']:5.2f}s → {out.name}")

    script["_tts_fallback"] = used_fallback
    total = sum(t["duration"] for t in tracks)
    print(f"Narration total ≈ {total:.1f}s ({len(tracks)} scenes)"
          + ("  [SILENT FALLBACK — no voice]" if used_fallback else ""))
    return tracks


def main() -> None:
    ap = argparse.ArgumentParser(description="Video script → per-scene Korean TTS")
    ap.add_argument("script", help="Path to script.json")
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--voice", help=f"edge-tts voice (default {VOICE_DEFAULT})")
    ap.add_argument("--allow-silent-fallback", action="store_true",
                    help="Emit silent tracks if the TTS endpoint is unreachable")
    args = ap.parse_args()

    script = json.loads(Path(args.script).read_text(encoding="utf-8"))
    synth(script, Path(args.outdir), allow_silent=args.allow_silent_fallback,
          voice=args.voice)
    Path(args.script).write_text(
        json.dumps(script, ensure_ascii=False, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
