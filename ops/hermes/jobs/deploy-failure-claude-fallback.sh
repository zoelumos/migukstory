#!/usr/bin/env bash
set -euo pipefail

# Watch Miguk Story deploy/publish workflows. On a new recent failure, hand the
# run to Claude Code for deterministic repair, then record the run ID so this
# watchdog never loops on the same failure.

REPO="/Users/zoelumos/migukstory"
OWNER_REPO="zoelumos/migukstory"
STATE_DIR="$REPO/ops/hermes/state"
LOG_DIR="$REPO/ops/hermes/logs"
STATE_FILE="$STATE_DIR/deploy-failure-claude-fallback.seen"
LOG_FILE="$LOG_DIR/deploy-failure-claude-fallback-$(date -u +%Y%m%d).log"
WORKFLOWS=("Deploy to Cloudflare Pages" "Daily post from queue")
MAX_AGE_HOURS="${MAX_AGE_HOURS:-12}"

mkdir -p "$STATE_DIR" "$LOG_DIR"
touch "$STATE_FILE"

log() {
  printf '[%s] %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" >> "$LOG_FILE"
}

notify() {
  local line
  line="[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*"
  printf '%s\n' "$line" | tee -a "$LOG_FILE"
}

if ! command -v gh >/dev/null 2>&1; then
  notify "BLOCKED: gh CLI not found"
  exit 2
fi
if ! command -v claude >/dev/null 2>&1; then
  notify "BLOCKED: claude CLI not found"
  exit 2
fi

cd "$REPO"

cutoff_epoch=$(python3 - <<PY
from datetime import datetime, timedelta, timezone
print(int((datetime.now(timezone.utc) - timedelta(hours=float('$MAX_AGE_HOURS'))).timestamp()))
PY
)

handled=0
for workflow in "${WORKFLOWS[@]}"; do
  runs_json=$(gh run list --repo "$OWNER_REPO" --workflow "$workflow" --status failure --limit 5 --json databaseId,createdAt,headBranch,headSha,url,conclusion,status,name 2>>"$LOG_FILE" || true)
  if [ -z "$runs_json" ] || [ "$runs_json" = "[]" ]; then
    continue
  fi

  while IFS=$'\t' read -r run_id created_at branch sha url name; do
    [ -z "${run_id:-}" ] && continue
    if grep -qx "$run_id" "$STATE_FILE"; then
      continue
    fi
    run_epoch=$(python3 - <<PY
from datetime import datetime
s = '$created_at'.replace('Z', '+00:00')
print(int(datetime.fromisoformat(s).timestamp()))
PY
)
    if [ "$run_epoch" -lt "$cutoff_epoch" ]; then
      log "SKIP old failure run=$run_id workflow=$workflow created=$created_at"
      echo "$run_id" >> "$STATE_FILE"
      continue
    fi

    notify "NEW Migukstory failure detected: workflow=$workflow run=$run_id branch=$branch url=$url"
    tmp_log="/tmp/migukstory-gh-run-${run_id}.log"
    gh run view "$run_id" --repo "$OWNER_REPO" --log > "$tmp_log" 2>>"$LOG_FILE" || true

    prompt="Miguk Story deploy/publish failed. Repo: $REPO. Failed workflow: $workflow. Run ID: $run_id. URL: $url. Branch: $branch. SHA: $sha. Inspect the repo and the saved failure log at $tmp_log. Fix only deterministic repo/content/workflow issues that caused this run to fail. Do not print secrets. Run python3 scripts/validate_markdown_frontmatter.py src/content/blog drafts queue and npm run build. If you make changes, commit and push to main with a clear fix message. If the failure is external/secrets/quota-only, do not edit; report the blocker. Keep changes bounded to this repo."

    set +e
    claude -p "$prompt" \
      --model opus \
      --effort max \
      --allowedTools 'Read,Write,Edit,MultiEdit,Bash(git *),Bash(gh run view*),Bash(npm *),Bash(node *),Bash(python3 *),Bash(chmod *),Bash(cat *),Bash(sed *)' \
      --max-turns 18 \
      --output-format text >> "$LOG_FILE" 2>&1
    claude_status=$?
    set -e

    echo "$run_id" >> "$STATE_FILE"
    handled=$((handled + 1))
    notify "Claude fallback finished for Migukstory run=$run_id status=$claude_status"
  done < <(RUNS_JSON="$runs_json" python3 - <<'PY'
import json, os
for r in json.loads(os.environ.get('RUNS_JSON', '[]')):
    print('\t'.join(str(r.get(k, '')) for k in ['databaseId','createdAt','headBranch','headSha','url','name']))
PY
)
done

if [ "$handled" -eq 0 ]; then
  log "OK: no new recent failed deploy/publish runs."
fi
