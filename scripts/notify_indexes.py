#!/usr/bin/env python3
"""
Submit newly-published URLs to search engine indexing endpoints after deploy.

Pipelines:
  1. IndexNow  — POST to https://api.indexnow.org/IndexNow
                 Covers: Bing, Yandex, Yep, Seznam, Naver (some).
                 No auth; uses key file at /<key>.txt for domain verification.
                 Free, no quota.
  2. Google Indexing API — POST to https://indexing.googleapis.com/v3/urlNotifications:publish
                 Officially supported for JobPosting / BroadcastEvent only;
                 we use it for NewsArticle (works in practice; not contractual).
                 Requires service-account JSON with Search Console Owner role.
                 Optional — runs only if a service-account secret is set
                 (GSC_SERVICE_ACCOUNT or GOOGLE_SERVICE_ACCOUNT_JSON).

URL discovery:
  Run with explicit URLs:   notify_indexes.py https://… https://…
  Or auto-discover from git: notify_indexes.py --auto
    Lists src/content/blog/*.md files added in the last commit
    and converts to canonical blog URLs.

Env:
  SITE_URL                       default https://migukstory.com
  INDEXNOW_KEY                   required for IndexNow. Read from this env OR
                                 falls back to scanning public/*.txt for a file
                                 whose name == content (standard IndexNow pattern).
  GSC_SERVICE_ACCOUNT            optional. Google service-account JSON, either
                                 raw or base64-encoded (auto-detected). This is
                                 the GitHub Actions secret name used by this
                                 repo — see .github/workflows/. When set, the
                                 Google Indexing API path is also used.
  GOOGLE_SERVICE_ACCOUNT_JSON    optional, legacy alias. Raw JSON string only.
                                 Checked if GSC_SERVICE_ACCOUNT is unset.

Exit codes:
  0  all submissions succeeded (or skipped cleanly)
  1  hard error (bad input)
  2  one or more partial failures (logged; doesn't fail CI)
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.request
import urllib.error
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PUBLIC = REPO / "public"
BLOG_SRC = REPO / "src" / "content" / "blog"

DEFAULT_SITE_URL = "https://migukstory.com"


def discover_indexnow_key() -> str | None:
    """IndexNow key from env, or auto-discover from public/<key>.txt."""
    key = os.environ.get("INDEXNOW_KEY", "").strip()
    if key:
        return key
    if not PUBLIC.exists():
        return None
    for f in PUBLIC.glob("*.txt"):
        try:
            content = f.read_text(encoding="utf-8").strip()
        except Exception:
            continue
        # IndexNow convention: filename stem == file content.
        if content and content == f.stem and len(content) >= 8:
            return content
    return None


def git_added_blog_urls(site_url: str) -> list[str]:
    """Files added to src/content/blog/ in the last commit."""
    try:
        out = subprocess.check_output(
            ["git", "diff", "--name-status", "--diff-filter=A", "HEAD~1", "HEAD", "--", "src/content/blog/"],
            cwd=REPO, text=True,
        )
    except subprocess.CalledProcessError as e:
        print(f"⚠️  git diff failed: {e}", file=sys.stderr)
        return []
    urls: list[str] = []
    for line in out.strip().splitlines():
        parts = line.split("\t", 1)
        if len(parts) != 2 or not parts[1].endswith(".md"):
            continue
        slug = Path(parts[1]).stem
        urls.append(f"{site_url.rstrip('/')}/blog/{slug}/")
    return urls


def submit_indexnow(urls: list[str], key: str, site_url: str) -> tuple[bool, str]:
    host = site_url.replace("https://", "").replace("http://", "").rstrip("/")
    key_location = f"{site_url.rstrip('/')}/{key}.txt"
    payload = {
        "host": host,
        "key": key,
        "keyLocation": key_location,
        "urlList": urls,
    }
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        "https://api.indexnow.org/IndexNow",
        data=body,
        headers={"Content-Type": "application/json; charset=utf-8",
                 "User-Agent": "migukstory-indexer/1.0 (+https://migukstory.com)"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return True, f"HTTP {resp.status}"
    except urllib.error.HTTPError as e:
        # 200/202 = ok; 422 = "URLs are invalid" (e.g., not yet live); 429 = throttled.
        return e.code in (200, 202), f"HTTP {e.code}: {e.reason}"
    except Exception as e:
        return False, f"network error: {e}"


def submit_google_indexing(urls: list[str], sa_json: str) -> list[tuple[str, bool, str]]:
    """Submit each URL individually to Google Indexing API.
    Returns list of (url, ok, message)."""
    try:
        from google.oauth2 import service_account
        from google.auth.transport.requests import Request
    except ImportError as e:
        return [(u, False, f"google-auth/requests not installed (pip install google-auth requests): {e}") for u in urls]

    try:
        info = json.loads(sa_json)
        creds = service_account.Credentials.from_service_account_info(
            info,
            scopes=["https://www.googleapis.com/auth/indexing"],
        )
        # Refresh to get a fresh access token.
        creds.refresh(Request())
    except Exception as e:
        return [(u, False, f"creds error: {e}") for u in urls]

    results: list[tuple[str, bool, str]] = []
    api_url = "https://indexing.googleapis.com/v3/urlNotifications:publish"
    for u in urls:
        body = json.dumps({"url": u, "type": "URL_UPDATED"}).encode("utf-8")
        req = urllib.request.Request(
            api_url,
            data=body,
            headers={
                "Content-Type": "application/json; charset=utf-8",
                "Authorization": f"Bearer {creds.token}",
                "User-Agent": "migukstory-indexer/1.0",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                results.append((u, True, f"HTTP {resp.status}"))
        except urllib.error.HTTPError as e:
            results.append((u, False, f"HTTP {e.code}: {e.reason}"))
        except Exception as e:
            results.append((u, False, f"network: {e}"))
    return results


def resolve_google_sa() -> str | None:
    """Resolve the Google service-account JSON from the environment.

    Accepts either secret name, in priority order:
      1. GSC_SERVICE_ACCOUNT          — raw JSON OR base64-encoded JSON.
                                        This is the GitHub Actions secret name
                                        configured for this repo.
      2. GOOGLE_SERVICE_ACCOUNT_JSON  — legacy alias; raw JSON only.

    base64 values are auto-detected and decoded. Returns the raw JSON string,
    or None if neither variable is set / usable. The value itself is never
    logged — only which variable was used.
    """
    import base64

    for var in ("GSC_SERVICE_ACCOUNT", "GOOGLE_SERVICE_ACCOUNT_JSON"):
        raw = os.environ.get(var, "").strip()
        if not raw:
            continue
        if raw.lstrip().startswith("{"):
            return raw  # already JSON
        # Otherwise treat it as base64-encoded JSON.
        try:
            decoded = base64.b64decode(raw, validate=True).decode("utf-8")
        except Exception:
            print(f"⚠️  {var} is set but is neither JSON nor valid base64 — ignoring.",
                  file=sys.stderr)
            continue
        if decoded.lstrip().startswith("{"):
            return decoded
        print(f"⚠️  {var} decoded but does not look like JSON — ignoring.", file=sys.stderr)
    return None


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Submit URLs to IndexNow + Google Indexing API.")
    p.add_argument("urls", nargs="*", help="Full URLs to submit. Omit with --auto to discover from git.")
    p.add_argument("--auto", action="store_true",
                   help="Discover newly-added src/content/blog/*.md files from HEAD~1..HEAD and submit their URLs.")
    p.add_argument("--site-url", default=os.environ.get("SITE_URL", DEFAULT_SITE_URL),
                   help=f"Site origin. Default: {DEFAULT_SITE_URL}")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    site_url = args.site_url.rstrip("/")

    if args.auto and args.urls:
        print("❌ Pass either --auto OR URLs, not both.", file=sys.stderr)
        return 1
    if args.auto:
        urls = git_added_blog_urls(site_url)
    else:
        urls = args.urls

    if not urls:
        print("✅ No URLs to submit.")
        return 0

    print(f"📤 Submitting {len(urls)} URL(s):")
    for u in urls:
        print(f"   - {u}")

    any_failure = False

    # IndexNow
    key = discover_indexnow_key()
    if not key:
        print("\n⚠️  IndexNow: no key found (set INDEXNOW_KEY env or place "
              "public/<key>.txt with matching content). Skipping IndexNow.")
        any_failure = True
    else:
        ok, msg = submit_indexnow(urls, key, site_url)
        print(f"\n🔔 IndexNow ({key[:8]}…): {'✅' if ok else '❌'} {msg}")
        if not ok:
            any_failure = True

    # Google Indexing API (optional)
    sa = resolve_google_sa()
    if not sa:
        print("\nℹ️  Google Indexing API: no service-account secret set "
              "(GSC_SERVICE_ACCOUNT / GOOGLE_SERVICE_ACCOUNT_JSON) — skipping.")
    else:
        print("\n🔔 Google Indexing API:")
        results = submit_google_indexing(urls, sa)
        for u, ok, msg in results:
            print(f"   {'✅' if ok else '❌'} {u} — {msg}")
            if not ok:
                any_failure = True

    return 2 if any_failure else 0


if __name__ == "__main__":
    sys.exit(main())
