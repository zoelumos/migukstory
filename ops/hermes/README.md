# ops/hermes — cron job definitions for Hermes agent

This folder is the **source of truth** for migukstory.com's recurring operational
tasks running on Steve's Mac mini via Hermes + `claude -p`.

## Architecture

```
Hermes agent (on Mac mini, 24/7)
  │
  │  reads
  ▼
ops/hermes/jobs/*.yml         ← job definitions (this folder)
  │
  │  schedules via crontab / launchd
  ▼
cron tick fires the `command` field of each job
  │
  ▼
For Claude-driven jobs:
    claude -p "$(cat ops/hermes/prompts/<job>.md)" --output-format text \
      >> ops/hermes/logs/<job>-YYYYMMDD.log 2>&1

For pure-shell jobs:
    gh workflow run ...  (or similar)
```

The Mac mini already has:
- `claude` CLI installed (uses Steve's Max subscription auth, **no API key needed**)
- `gh` CLI authenticated as `zoelumos`
- `git` configured
- The repo cloned at `/Users/zoelumos/migukstory`

## Why this design

- **No `ANTHROPIC_API_KEY` required** — `claude -p` uses your Max subscription via the local Claude install.
- **Version-controlled** — every prompt and schedule lives in the repo. Edit → `git push` → next cron tick uses the new version (after Hermes `git pull`).
- **Auditable** — every run produces a dated log in `ops/hermes/logs/`. Easy to grep for failures.
- **No remote dependencies** — doesn't need claude.ai routines, MCP connectors, or any cloud secret.

## Mac mini prerequisites (one-time setup)

```bash
# Prevent system sleep so cron fires reliably
sudo pmset -a sleep 0 disksleep 0 womp 1 powernap 1

# Verify CLIs
claude --version
gh auth status
git -C /Users/zoelumos/migukstory status

# Recommended: pre-approve common tools for claude -p so it doesn't prompt
# (~/.claude/settings.json has the permissions allowlist)
```

## How Hermes should consume this folder

1. **On each Hermes setup run**: `git pull` to get latest schedules and prompts.
2. **For each file in `jobs/*.yml`**:
   - Parse `schedule` (cron expression, UTC)
   - Convert to Mac mini's local timezone if Mac isn't running in UTC
   - Install/update the cron entry (or launchd plist) with the `command` field
   - Use `name` as the cron entry's identifier (so re-runs are idempotent)
3. **On failure** (non-zero exit code): forward the last 50 lines of the log to the configured `on_failure.slack` channel (or whatever notification mechanism Hermes uses).
4. **Daily**: rotate logs older than 30 days (rm).

## The drafting pipeline (uses Max, not API)

The `daily-ingest.yml` job runs the full sequential pipeline: `scripts/draft_from_rss.py` → `scripts/improve_drafts.py` → `scripts/editor_grade.py` → immediate read-only editorial brief, with the env var `CLAUDE_VIA_CLI=1`. Both scripts have been modified to:

- **Default behavior** (env var unset): call `api.anthropic.com` via the Anthropic SDK → needs `ANTHROPIC_API_KEY`.
- **CLAUDE_VIA_CLI=1**: shell out to `claude -p "..."` instead → uses local Max-subscription auth, no API key.

So Hermes can drive the entire drafting pipeline on the Mac mini using only Steve's Max
subscription. The same scripts work in GitHub Actions too (with the env var unset and
`ANTHROPIC_API_KEY` set), so this is non-breaking.

The route logic is in `scripts/draft_from_rss.py::call_claude` and
`scripts/editor_grade.py::call_claude`:

```python
def call_claude(...):
    if os.environ.get("CLAUDE_VIA_CLI", "").strip() == "1":
        return _call_claude_via_cli(...)  # subprocess to `claude -p`
    return _call_claude_via_api(...)      # original SDK path
```

---

## Job schema (each `jobs/*.yml`)

```yaml
name: migukstory-<job-id>          # unique, kebab-case, used as cron identifier
description: <one-line description>
schedule: "<cron expression>"      # 5-field, UTC
timezone: UTC                      # always UTC in the file; Hermes converts
working_dir: /Users/zoelumos/migukstory
command: |
  <multi-line shell command>
prompt_file: prompts/<job>.md      # optional, only for Claude-driven jobs
log_file: logs/<job>-{date}.log    # where to capture stdout+stderr
on_failure:
  notify: slack                    # slack | email | none
  channel_or_recipient: "#migukstory-ops"
  message: "<brief failure message>"
prerequisites:
  - gh CLI authenticated as zoelumos
  - claude CLI working (claude --version returns successfully)
  - /Users/zoelumos/migukstory exists and is on main
```

## Job inventory

| File | Schedule (UTC) | Local approx (ET, EDT) | Purpose | Uses Claude? |
|---|---|---|---|---|
| `daily-ingest.yml` | `0 11 * * *` | 7:00 AM | **RSS → draft → validate/improve → editor grade → immediate editorial brief → open PR** (sequential pipeline) | Yes (`claude -p`, Max auth) |
| `daily-publish.yml` | `0 12 * * *` | 8:00 AM | Trigger `daily-post.yml` workflow → publish 1 from queue | No (gh CLI only) |
| `daily-editorial-review.yml` | disabled | n/a | Standalone review disabled; invoked immediately by `daily-ingest` after fresh grading | Yes |
| `daily-health.yml` | `30 14 * * *` | 10:30 AM | Status snapshot (workflows, site, queue depth, drafts pending) | Yes |
| `weekly-audit.yml` | `0 15 * * 1` | Mon 11:00 AM | Weekly content stats in Korean | Yes |
| `monthly-cf-rotate.yml` | `0 14 1 * *` | 1st 10:00 AM | Reminder to rotate Cloudflare API token | No (just message) |

Note: cron is fixed UTC. Local time will drift 1 hour earlier in winter (EST = UTC−5). If
year-round 8/9/10:30 AM ET is desired, Hermes should re-render the cron with DST awareness.

## Adding a new job

1. Create `jobs/<new-job>.yml` matching the schema above.
2. If Claude-driven, also create `prompts/<new-job>.md` with the prompt content.
3. Commit + push.
4. On next Hermes refresh, the new job appears in the schedule.

## Disabling a job temporarily

Set `enabled: false` at the top of the job's YAML. Hermes should respect it and skip
installing/firing that job. Doesn't delete history.

## Local manual testing

To test a Claude-driven job before scheduling:

```bash
cd /Users/zoelumos/migukstory
claude -p "$(cat ops/hermes/prompts/daily-editorial-review.md)" \
  --output-format text \
  --max-turns 10
```

If the output looks right, the schedule will produce the same thing daily.

## Related — what this folder does NOT manage

These automations live elsewhere and are independent of Hermes:

- `.github/workflows/daily-draft.yml` — RSS → AI draft → editor grade → auto-PR
  (runs in GitHub Actions cloud, on its own cron every 4 hours)
- `.github/workflows/cloudflare-deploy.yml` — build + deploy on push to main
- `.github/workflows/daily-post.yml` — queue → blog publisher (triggered BY this folder's
  daily-publish job, but the workflow itself runs in GH cloud)

All three keep running regardless of Hermes / Mac mini state. This folder only owns
the operational gluing layer (publish trigger, health checks, audits, reminders).
