#!/bin/bash
# Generic Hermes job runner. Usage: run-job.sh <job-name>
# Reads ops/hermes/jobs/<job-name>.yml and executes its `command` field in
# `working_dir`, logging stdout+stderr to ops/hermes/logs/<job>-YYYYMMDD.log.
# Installed into crontab by ops/hermes/bin/install-cron.py.

# cron runs with a minimal PATH — set an explicit one covering all tools.
export PATH="/Users/zoelumos/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

set -uo pipefail

JOB="${1:?usage: run-job.sh <job-name>}"
REPO="/Users/zoelumos/migukstory"
JOBFILE="$REPO/ops/hermes/jobs/${JOB}.yml"
LOGDIR="$REPO/ops/hermes/logs"
mkdir -p "$LOGDIR"
LOG="$LOGDIR/${JOB}-$(date +%Y%m%d).log"

run() {
  echo "===== ${JOB} START $(date -u +%Y-%m-%dT%H:%M:%SZ) ====="
  if [ ! -f "$JOBFILE" ]; then
    echo "ERROR: job file not found: $JOBFILE"
    return 1
  fi
  local enabled workdir cmd rc
  enabled=$(/usr/bin/python3 -c "import yaml;print(yaml.safe_load(open('$JOBFILE')).get('enabled',True))")
  if [ "$enabled" != "True" ]; then
    echo "job disabled (enabled: false) — skipping."
    return 0
  fi
  workdir=$(/usr/bin/python3 -c "import yaml;print(yaml.safe_load(open('$JOBFILE')).get('working_dir','$REPO'))")
  cmd=$(/usr/bin/python3 -c "import yaml,sys;sys.stdout.write(yaml.safe_load(open('$JOBFILE'))['command'])")
  cd "$workdir" || { echo "ERROR: cannot cd to $workdir"; return 1; }
  bash -c "$cmd"
  rc=$?
  echo "===== ${JOB} END rc=$rc $(date -u +%Y-%m-%dT%H:%M:%SZ) ====="
  return $rc
}

run >> "$LOG" 2>&1
exit $?
