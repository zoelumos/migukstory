# Deploy failure Claude fallback

Miguk Story uses this local Hermes/macOS watchdog to prevent a broken publish or Cloudflare Pages deploy from sitting unnoticed.

## What it watches

- GitHub Actions workflow: `Deploy to Cloudflare Pages`
- GitHub Actions workflow: `Daily post from queue`
- Only recent failures are considered (`MAX_AGE_HOURS`, default `12`).
- Run IDs are deduped in `ops/hermes/state/deploy-failure-claude-fallback.seen`.

## What it does on a new failure

1. Saves the failed GitHub Actions log to `/tmp/migukstory-gh-run-<RUN_ID>.log`.
2. Runs bounded Claude Code (`claude -p`) in `/Users/zoelumos/migukstory`.
3. Tells Claude to inspect the failure, fix deterministic repo/content/workflow issues, run:
   - `python3 scripts/validate_markdown_frontmatter.py src/content/blog drafts queue`
   - `npm run build`
4. If changes are needed, Claude may commit and push to `main`.
5. If the problem is external (secret/quota/provider outage), Claude should report the blocker and not edit.

Logs are written to `ops/hermes/logs/deploy-failure-claude-fallback-YYYYMMDD.log`.

## Manual test

```bash
cd /Users/zoelumos/migukstory
ops/hermes/jobs/deploy-failure-claude-fallback.sh
```

## Register with Hermes cron

Hermes cron scripts must live under `~/.hermes/scripts/`. Create a tiny wrapper first:

```bash
cat > ~/.hermes/scripts/migukstory-deploy-failure-claude-fallback.sh <<'SH'
#!/usr/bin/env bash
set -euo pipefail
exec /Users/zoelumos/migukstory/ops/hermes/jobs/deploy-failure-claude-fallback.sh
SH
chmod +x ~/.hermes/scripts/migukstory-deploy-failure-claude-fallback.sh
```

Then run every 15 minutes:

```python
cronjob(
  action="create",
  name="Migukstory deploy failure Claude fallback",
  schedule="every 15m",
  prompt="Run the Migukstory deploy failure fallback script. The script is quiet when there is no new failure and prints only when it handles a failure or hits a blocker.",
  script="migukstory-deploy-failure-claude-fallback.sh",
  no_agent=True,
  deliver="origin",
)
```

Current default-profile cron job ID: `54b7facb8e0f`.

Script stdout is intentionally quiet when there is no new failure, so `no_agent=True` cron runs will not spam Steve. It prints only when it handles a failure or hits a blocker.
