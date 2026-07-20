"""Upload a finished MP4 to YouTube via Data API v3 (OAuth refresh token).

Designed for unattended CI: a one-time OAuth consent produces a refresh token
that is stored as a GitHub secret; this script exchanges it for a short-lived
access token on every run — no browser. See docs/YOUTUBE-AUTOMATION.md for the
one-time token bootstrap.

Required env (any of the two credential shapes):
    YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN
  or
    YT_OAUTH_JSON  = base64 of {"client_id","client_secret","refresh_token"}

Quota: an upload costs ~1,600 units of the default 10,000/day → ~6 videos/day.

Usage:
    python -m scripts.youtube.upload_youtube video.mp4 --script script.json
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
from pathlib import Path

TOKEN_URI = "https://oauth2.googleapis.com/token"
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def _load_oauth() -> dict:
    blob = os.environ.get("YT_OAUTH_JSON")
    if blob:
        try:
            data = json.loads(base64.b64decode(blob))
        except Exception:
            data = json.loads(blob)
    else:
        data = {
            "client_id": os.environ.get("YT_CLIENT_ID", ""),
            "client_secret": os.environ.get("YT_CLIENT_SECRET", ""),
            "refresh_token": os.environ.get("YT_REFRESH_TOKEN", ""),
        }
    missing = [k for k in ("client_id", "client_secret", "refresh_token") if not data.get(k)]
    if missing:
        raise SystemExit(
            "Missing YouTube OAuth credentials: " + ", ".join(missing) +
            "\nSet YT_CLIENT_ID / YT_CLIENT_SECRET / YT_REFRESH_TOKEN "
            "(or YT_OAUTH_JSON). See docs/YOUTUBE-AUTOMATION.md."
        )
    return data


def build_service(oauth: dict):
    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
    except ImportError as exc:
        raise SystemExit(
            "google-api-python-client + google-auth required:\n"
            "  pip install google-api-python-client google-auth google-auth-httplib2"
        ) from exc

    creds = Credentials(
        token=None,
        refresh_token=oauth["refresh_token"],
        client_id=oauth["client_id"],
        client_secret=oauth["client_secret"],
        token_uri=TOKEN_URI,
        scopes=SCOPES,
    )
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def upload(video: Path, meta: dict, privacy: str | None = None) -> str:
    # Validate credentials first, then the SDK (build_service prints the exact
    # pip line), so the failure message matches what's actually missing.
    oauth = _load_oauth()
    youtube = build_service(oauth)
    from googleapiclient.http import MediaFileUpload

    body = {
        "snippet": {
            "title": meta.get("title", video.stem)[:100],
            "description": meta.get("description", ""),
            "tags": meta.get("tags", [])[:15],
            "categoryId": str(meta.get("categoryId", "25")),
            "defaultLanguage": "ko",
            "defaultAudioLanguage": "ko",
        },
        "status": {
            "privacyStatus": privacy or meta.get("privacyStatus", "private"),
            "selfDeclaredMadeForKids": False,
        },
    }
    media = MediaFileUpload(str(video), chunksize=-1, resumable=True,
                            mimetype="video/mp4")
    request = youtube.videos().insert(
        part="snippet,status", body=body, media_body=media
    )

    print(f"Uploading {video.name} ({video.stat().st_size/1e6:.1f} MB) → YouTube …")
    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"  {int(status.progress()*100)}%")
    vid = response["id"]
    url = f"https://youtu.be/{vid}"
    print(f"✅ Uploaded: {url}  (privacy={body['status']['privacyStatus']})")
    return url


def main() -> None:
    ap = argparse.ArgumentParser(description="Upload MP4 to YouTube (Data API v3)")
    ap.add_argument("video", help="Path to .mp4")
    ap.add_argument("--script", help="script.json to read video metadata from")
    ap.add_argument("--title")
    ap.add_argument("--privacy", choices=["private", "unlisted", "public"])
    args = ap.parse_args()

    meta: dict = {}
    if args.script:
        meta = json.loads(Path(args.script).read_text(encoding="utf-8")).get("video", {})
    if args.title:
        meta["title"] = args.title
    if not meta.get("title"):
        meta["title"] = Path(args.video).stem

    url = upload(Path(args.video), meta, privacy=args.privacy)
    # Emit for GitHub Actions step outputs.
    gh_out = os.environ.get("GITHUB_OUTPUT")
    if gh_out:
        with open(gh_out, "a", encoding="utf-8") as fh:
            fh.write(f"youtube_url={url}\n")
    print(url)


if __name__ == "__main__":
    main()
