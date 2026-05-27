# /goal — Migukstory full automation directive

When this command is invoked, treat the following as the active project goal and quality bar.

## Goal

Migukstory must be a **complete end-to-end automated publishing and indexing system**, not a semi-manual workflow.

Normal success path:

```txt
ingest → source validation → Claude draft/review → quality gate → queue/PR/merge → publish → build → deploy → RSS/sitemap → Google Search Console sitemap submit → IndexNow/Indexing API → live URL verification → Korean status/error notification
```

## Required behavior

- Do not design fixes that rely on Steve manually saying “publish now”.
- Do not stop at draft generation, PR merge, or GitHub Action success.
- Treat the job as incomplete until live URL, RSS, sitemap, and indexing-notification path are verified.
- Sitemap is mission-critical for this new Google site.
- Published content must never remain `draft: true`.
- Publish workflows must be race-safe and must not get stranded by detached HEAD, duplicate runs, dirty worktrees, or hidden queue leftovers.
- Failures must be loud: Korean status/error notification with the failing stage and next recovery step.
- Follow Google new-site basics: crawlable pages, stable canonical URLs, clean sitemap, helpful/original Korean-American content, strong internal links, no spammy backlinks or thin-content bursts.

## Review response format

Return:

```txt
GOAL STATUS: PASS/FAIL
AUTOMATION GAP: ...
SITEMAP/INDEXING STATUS: ...
MUST-FIX NOW: ...
NEXT PATCH: ...
```

If any part of ingest→publish→deploy→sitemap→index verification needs Steve to manually kick it every day, mark the goal as FAIL.
