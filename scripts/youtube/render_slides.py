"""Render each video-script scene to a 1080x1920 PNG via headless Chromium.

Migukstory's product edge is *visual explanation*, so slides are the point —
not stock b-roll. Each scene kind (hook / points / table / steps / cta) has a
dedicated HTML template styled with the article's category color. Headless
Chromium screenshots the fixed 1080x1920 canvas; Korean text needs a CJK font
installed (fonts-nanum / fonts-noto-cjk on CI).

Usage:
    python -m scripts.youtube.render_slides script.json --outdir build/youtube/<slug>
"""

from __future__ import annotations

import argparse
import html
import json
import subprocess
import sys
import tempfile
from pathlib import Path

if __package__:
    from .config import HEIGHT, WIDTH, find_chromium
else:  # pragma: no cover
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from config import HEIGHT, WIDTH, find_chromium  # type: ignore


def _esc(s: str) -> str:
    return html.escape(str(s), quote=True)


# ── Per-scene HTML bodies ──────────────────────────────────────────────────
def _hook_html(sc: dict, color: str, badge: str) -> str:
    return f"""
    <div class="badge" style="background:{color}">{_esc(badge)}</div>
    <div class="hook-headline">{_esc(sc['headline'])}</div>
    <div class="hook-sub">{_esc(sc.get('sub',''))}</div>
    <div class="pulse">지금 확인 &rarr;</div>
    """


def _points_html(sc: dict, color: str, badge: str) -> str:
    items = "".join(
        f'<li><span class="mk" style="color:{color}">●</span>{_esc(b)}</li>'
        for b in sc["bullets"]
    )
    return f"""
    <div class="badge" style="background:{color}">{_esc(badge)}</div>
    <div class="scene-title">{_esc(sc['title'])}</div>
    <ul class="points">{items}</ul>
    """


def _clip(text: str, n: int = 30) -> str:
    text = str(text)
    return text if len(text) <= n else text[: n - 1].rstrip() + "…"


def _table_html(sc: dict, color: str, badge: str) -> str:
    headers = sc.get("headers", [])
    thead = "".join(f"<th>{_esc(_clip(h, 12))}</th>" for h in headers)
    body_rows = ""
    for r in sc["rows"]:
        cells = "".join(f"<td>{_esc(_clip(c, 30))}</td>" for c in r)
        body_rows += f"<tr>{cells}</tr>"
    return f"""
    <div class="badge" style="background:{color}">{_esc(badge)}</div>
    <div class="scene-title">{_esc(sc['title'])}</div>
    <table style="--accent:{color}">
      <thead><tr>{thead}</tr></thead>
      <tbody>{body_rows}</tbody>
    </table>
    """


def _steps_html(sc: dict, color: str, badge: str) -> str:
    items = ""
    for i, step in enumerate(sc["steps"], 1):
        items += (
            f'<li><span class="num" style="background:{color}">{i}</span>'
            f'<span class="step-txt">{_esc(step)}</span></li>'
        )
    return f"""
    <div class="badge" style="background:{color}">{_esc(badge)}</div>
    <div class="scene-title">{_esc(sc['title'])}</div>
    <ol class="steps">{items}</ol>
    """


def _cta_html(sc: dict, color: str, badge: str) -> str:
    return f"""
    <div class="cta-wrap">
      <div class="cta-head">{_esc(sc['headline'])}</div>
      <div class="cta-site" style="color:{color}">{_esc(sc.get('sub',''))}</div>
      <div class="cta-sub">이민 · 세금 · 건강보험 · 경제<br>한인 생활정보를 쉽게</div>
      <div class="cta-btn" style="background:{color}">구독 &amp; 알림 설정 🔔</div>
    </div>
    """


_RENDERERS = {
    "hook": _hook_html,
    "points": _points_html,
    "table": _table_html,
    "steps": _steps_html,
    "cta": _cta_html,
}


def _page(inner: str, color: str, caption: str = "") -> str:
    """Wrap a scene body in the fixed 1080x1920 branded canvas.

    The spoken `caption` is baked into a bottom band (over a translucent
    gradient, the way Shorts captions sit over video). Baking it in the same
    Chromium pass avoids ffmpeg drawtext, which cannot auto-wrap Korean.
    """
    caption_band = (
        f'<div class="caption">{_esc(caption)}</div>' if caption else ""
    )
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  html,body {{ width:{WIDTH}px; height:{HEIGHT}px; overflow:hidden; }}
  body {{
    background:
      radial-gradient(1200px 800px at 50% -10%, {color}33, transparent 60%),
      linear-gradient(160deg, #0b1120 0%, #0f172a 55%, #020617 100%);
    color:#f8fafc;
    font-family:'Noto Sans KR','NanumGothic','Noto Sans CJK KR',sans-serif;
    /* keep-all stops Korean words from breaking mid-word (유효 → 유\n효). */
    word-break:keep-all; overflow-wrap:break-word;
    display:flex; flex-direction:column; justify-content:center;
    padding:120px 90px 430px; gap:44px;
  }}
  .badge {{
    align-self:flex-start; font-size:40px; font-weight:800; color:#fff;
    padding:16px 40px; border-radius:999px; letter-spacing:1px;
    box-shadow:0 8px 30px #0008;
  }}
  .hook-headline {{ font-size:104px; font-weight:900; line-height:1.15;
    letter-spacing:-1px; text-shadow:0 4px 24px #0009; }}
  .hook-sub {{ font-size:56px; font-weight:600; line-height:1.4; color:#cbd5e1; }}
  .pulse {{ margin-top:24px; font-size:52px; font-weight:800; color:#fde68a; }}
  .scene-title {{ font-size:74px; font-weight:900; line-height:1.2;
    letter-spacing:-1px; padding-bottom:12px; }}
  ul.points {{ list-style:none; display:flex; flex-direction:column; gap:40px; }}
  ul.points li {{ font-size:56px; font-weight:600; line-height:1.35;
    display:flex; gap:28px; align-items:flex-start; color:#e2e8f0; }}
  ul.points .mk {{ font-size:44px; line-height:1.5; flex:0 0 auto; }}
  table {{ width:100%; border-collapse:separate; border-spacing:0;
    font-size:40px; border-radius:28px; overflow:hidden;
    box-shadow:0 16px 50px #0009; table-layout:fixed; }}
  thead th {{ background:var(--accent); color:#fff; font-weight:800;
    padding:28px 26px; text-align:left; font-size:38px; }}
  thead th:first-child {{ width:44%; }}
  tbody td {{ padding:26px; border-top:2px solid #1e293b; color:#e2e8f0;
    background:#0f172aee; line-height:1.3; vertical-align:top; }}
  tbody tr:nth-child(even) td {{ background:#111c34ee; }}
  tbody td:first-child {{ font-weight:700; color:#f8fafc; }}
  ol.steps {{ list-style:none; display:flex; flex-direction:column; gap:38px;
    counter-reset:step; }}
  ol.steps li {{ display:flex; gap:34px; align-items:flex-start;
    font-size:52px; font-weight:600; line-height:1.35; color:#e2e8f0; }}
  ol.steps .num {{ flex:0 0 auto; width:88px; height:88px; border-radius:50%;
    color:#fff; font-weight:900; font-size:50px; display:flex;
    align-items:center; justify-content:center; box-shadow:0 6px 20px #0007; }}
  .step-txt {{ padding-top:14px; }}
  .cta-wrap {{ text-align:center; display:flex; flex-direction:column;
    align-items:center; gap:44px; }}
  .cta-head {{ font-size:76px; font-weight:800; color:#cbd5e1; }}
  .cta-site {{ font-size:120px; font-weight:900; letter-spacing:-2px; }}
  .cta-sub {{ font-size:52px; font-weight:600; color:#cbd5e1; line-height:1.5; }}
  .cta-btn {{ margin-top:30px; font-size:60px; font-weight:800; color:#fff;
    padding:36px 70px; border-radius:999px; box-shadow:0 12px 40px #0009; }}
  .brand {{ position:absolute; bottom:48px; left:0; right:0; text-align:center;
    font-size:40px; font-weight:800; color:#64748b; letter-spacing:2px; }}
  .caption {{ position:absolute; left:0; right:0; bottom:130px;
    padding:44px 80px 30px; text-align:center;
    font-size:52px; font-weight:700; line-height:1.4; color:#fff;
    text-shadow:0 3px 14px #000c;
    background:linear-gradient(to top, #020617f2 20%, #020617cc 55%, transparent);
    min-height:230px; display:flex; align-items:flex-end;
    justify-content:center; }}
  .caption:empty {{ display:none; }}
</style></head><body>
  {inner}
  {caption_band}
  <div class="brand">MIGUKSTORY · 미국스토리</div>
</body></html>"""


def render_scene_html(scene: dict, color: str, badge: str) -> str:
    renderer = _RENDERERS.get(scene["kind"], _points_html)
    # Hook and CTA already display their message large; the caption band is
    # for the content scenes (points/table/steps) where it aids retention.
    caption = "" if scene["kind"] in ("hook", "cta") else (scene.get("narration") or "")
    return _page(renderer(scene, color, badge), color, caption)


def render_slides(script: dict, outdir: Path) -> list[Path]:
    outdir.mkdir(parents=True, exist_ok=True)
    chromium = find_chromium()
    color = script.get("color", "#0f172a")
    badge = script.get("badge", "미국생활")
    slides: list[Path] = []

    with tempfile.TemporaryDirectory() as td:
        for i, scene in enumerate(script["scenes"]):
            html_doc = render_scene_html(scene, color, badge)
            html_path = Path(td) / f"scene_{i:02d}.html"
            html_path.write_text(html_doc, encoding="utf-8")
            png_path = outdir / f"scene_{i:02d}_{scene['id']}.png"
            cmd = [
                chromium, "--headless=new", "--no-sandbox", "--disable-gpu",
                "--hide-scrollbars", "--disable-dev-shm-usage",
                "--force-device-scale-factor=1",
                f"--window-size={WIDTH},{HEIGHT}",
                f"--screenshot={png_path}",
                f"file://{html_path}",
            ]
            res = subprocess.run(cmd, capture_output=True, text=True)
            if not png_path.exists():
                raise RuntimeError(
                    f"Chromium failed on scene {i} ({scene['id']}): {res.stderr[-500:]}"
                )
            scene["slide"] = str(png_path)
            slides.append(png_path)
            print(f"  slide {i:02d} [{scene['kind']:6}] → {png_path.name}")
    return slides


def main() -> None:
    ap = argparse.ArgumentParser(description="Video script JSON → slide PNGs")
    ap.add_argument("script", help="Path to script.json from article_to_script")
    ap.add_argument("--outdir", required=True, help="Directory for slide PNGs")
    args = ap.parse_args()

    script = json.loads(Path(args.script).read_text(encoding="utf-8"))
    slides = render_slides(script, Path(args.outdir))
    # Persist slide paths back into the script for the next stage.
    Path(args.script).write_text(
        json.dumps(script, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Rendered {len(slides)} slides → {args.outdir}")


if __name__ == "__main__":
    main()
