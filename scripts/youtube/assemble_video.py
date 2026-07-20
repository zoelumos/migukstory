"""Assemble slides + narration into the final vertical MP4 (ffmpeg).

Per scene: the slide PNG is shown for max(narration, min_display) seconds with
a slow Ken-Burns zoom for motion, paired with that scene's audio. Segments are
concatenated into one 1080x1920 H.264 file ready for YouTube Shorts upload.
Captions are already baked into the slides (see render_slides), so no fragile
drawtext step is needed here.

Usage:
    python -m scripts.youtube.assemble_video script.json --out build/youtube/<slug>/video.mp4
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

if __package__:
    from .config import FPS, HEIGHT, WIDTH, find_ffmpeg
else:  # pragma: no cover
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from config import FPS, HEIGHT, WIDTH, find_ffmpeg  # type: ignore


def _scene_duration(scene: dict) -> float:
    audio = float(scene.get("duration", 0) or 0)
    return round(max(audio, float(scene.get("min_display", 3.0))), 2)


def _build_segment(ff: str, slide: Path, audio: Path | None, seconds: float,
                   zoom_in: bool, out: Path) -> None:
    """Render one scene segment: still slide + slow zoom + its audio track."""
    frames = max(1, int(seconds * FPS))
    # Ken Burns: gently zoom 1.00→1.06 (or reverse), re-centered, no jitter.
    if zoom_in:
        z = "min(zoom+0.0007,1.06)"
    else:
        z = "if(eq(on,0),1.06,max(zoom-0.0007,1.00))"
    vf = (
        f"scale={WIDTH*2}:{HEIGHT*2},"
        f"zoompan=z='{z}':d={frames}:s={WIDTH}x{HEIGHT}:fps={FPS}:"
        f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)',"
        f"format=yuv420p"
    )
    cmd = [ff, "-y", "-hide_banner", "-loglevel", "error",
           "-loop", "1", "-i", str(slide)]
    if audio is not None and Path(audio).exists():
        cmd += ["-i", str(audio)]
    else:
        cmd += ["-f", "lavfi", "-t", f"{seconds:.2f}",
                "-i", "anullsrc=r=44100:cl=stereo"]
    cmd += [
        "-t", f"{seconds:.2f}", "-vf", vf, "-r", str(FPS),
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "160k", "-ar", "44100", "-ac", "2",
        "-shortest", str(out),
    ]
    subprocess.run(cmd, check=True)


def assemble(script: dict, out_path: Path, music: Path | None = None) -> Path:
    ff = find_ffmpeg()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        segments: list[Path] = []
        for i, scene in enumerate(script["scenes"]):
            slide = Path(scene["slide"])
            audio = Path(scene["audio"]) if scene.get("audio") else None
            seconds = _scene_duration(scene)
            seg = tmp / f"seg_{i:02d}.mp4"
            _build_segment(ff, slide, audio, seconds, zoom_in=(i % 2 == 0), out=seg)
            segments.append(seg)
            print(f"  segment {i:02d} [{scene['kind']:6}] {seconds:5.2f}s")

        concat_list = tmp / "concat.txt"
        concat_list.write_text(
            "".join(f"file '{s}'\n" for s in segments), encoding="utf-8"
        )
        # Re-encode on concat so timestamps are clean and uniform.
        cmd = [ff, "-y", "-hide_banner", "-loglevel", "error",
               "-f", "concat", "-safe", "0", "-i", str(concat_list)]
        if music and Path(music).exists():
            # Duck bed music under narration at low volume.
            cmd += ["-stream_loop", "-1", "-i", str(music),
                    "-filter_complex",
                    "[1:a]volume=0.10[bg];[0:a][bg]amix=inputs=2:duration=first[a]",
                    "-map", "0:v", "-map", "[a]"]
        cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", "20",
                "-pix_fmt", "yuv420p", "-r", str(FPS),
                "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart",
                str(out_path)]
        subprocess.run(cmd, check=True)

    total = sum(_scene_duration(s) for s in script["scenes"])
    size_mb = out_path.stat().st_size / 1e6
    print(f"Assembled {out_path.name} — {total:.1f}s, {size_mb:.1f} MB, "
          f"{WIDTH}x{HEIGHT}@{FPS}fps")
    script["video"]["file"] = str(out_path)
    script["video"]["duration"] = round(total, 2)
    return out_path


def main() -> None:
    ap = argparse.ArgumentParser(description="Slides + audio → final MP4")
    ap.add_argument("script", help="Path to script.json (with slide/audio paths)")
    ap.add_argument("--out", required=True, help="Output .mp4 path")
    ap.add_argument("--music", help="Optional background music file (looped, ducked)")
    args = ap.parse_args()

    script = json.loads(Path(args.script).read_text(encoding="utf-8"))
    assemble(script, Path(args.out), music=Path(args.music) if args.music else None)
    Path(args.script).write_text(
        json.dumps(script, ensure_ascii=False, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
