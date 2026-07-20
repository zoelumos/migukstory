# scripts/youtube — Article → Korean YouTube Short

Turns a published Migukstory article into a vertical (1080×1920) Korean Short.
Full setup, OAuth, and operating notes: **[docs/YOUTUBE-AUTOMATION.md](../../docs/YOUTUBE-AUTOMATION.md)**.

```
make_video.py          orchestrator: slug → script → slides → tts → mp4 → (upload)
├─ article_to_script.py  .md frontmatter+body → scene breakdown + Korean narration
├─ render_slides.py      scenes → 1080×1920 PNG slides (headless Chromium)
├─ synth_tts.py          scenes → per-scene ko-KR narration (edge-tts, free)
├─ assemble_video.py     slides + audio → H.264 MP4 (Ken Burns + baked captions)
├─ upload_youtube.py     MP4 → YouTube Data API v3 (OAuth refresh token)
└─ config.py             canvas, voices, category colors, binary discovery
```

Quick start:

```bash
pip install -r scripts/youtube/requirements.txt
sudo apt-get install -y ffmpeg chromium-browser fonts-nanum fonts-noto-cjk  # Ubuntu
python -m scripts.youtube.make_video --latest            # newest post → build/youtube/<slug>/<slug>.mp4
python -m scripts.youtube.make_video --latest --upload --privacy private
```

Egress-restricted sandbox (no TTS host)? add `--allow-silent-fallback` to still
produce a timed, captioned MP4. Real voice narration runs in GitHub Actions.
