#!/usr/bin/env python3
"""Install/refresh migukstory Hermes cron entries from ops/hermes/jobs/*.yml.

Idempotent: removes any existing lines tagged `# migukstory-hermes:<name>`
and re-adds current ones. Converts each job's UTC cron schedule to the
machine's local timezone. Disabled jobs (enabled: false) are skipped.

Usage:  python3 ops/hermes/bin/install-cron.py [--dry-run]
"""
import datetime
import subprocess
import sys
from pathlib import Path

import yaml

REPO = Path("/Users/zoelumos/migukstory")
JOBS_DIR = REPO / "ops/hermes/jobs"
RUNNER = REPO / "ops/hermes/bin/run-job.sh"
MARKER = "# migukstory-hermes:"

# Local UTC offset, in whole hours (PDT = -7, EDT = -4, etc.)
_utcoff = datetime.datetime.now().astimezone().utcoffset()
OFFSET_H = int(_utcoff.total_seconds() // 3600)
TZNAME = datetime.datetime.now().astimezone().tzname()


def convert_cron(cron_utc: str) -> tuple[str, str]:
    """Convert a 5-field UTC cron expr to local time. Returns (local_cron, note)."""
    parts = cron_utc.split()
    if len(parts) != 5:
        return cron_utc, "unparseable (left as UTC)"
    m, h, dom, mon, dow = parts
    if h == "*" or not h.lstrip("-").isdigit():
        return cron_utc, "non-integer hour (left as UTC)"
    local_h = int(h) + OFFSET_H
    day_shift = 0
    while local_h < 0:
        local_h += 24
        day_shift -= 1
    while local_h >= 24:
        local_h -= 24
        day_shift += 1
    note = f"UTC {h}:{m} -> {TZNAME} {local_h}:{m}"
    if day_shift:
        note += f"  WARNING: day rolls {day_shift:+d} — dom/dow NOT auto-adjusted"
    return f"{m} {local_h} {dom} {mon} {dow}", note


def load_jobs() -> list[dict]:
    jobs = []
    for f in sorted(JOBS_DIR.glob("*.yml")):
        d = yaml.safe_load(f.read_text())
        d["_file"] = f.name
        d["_stem"] = f.stem
        jobs.append(d)
    return jobs


def current_crontab() -> list[str]:
    r = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    if r.returncode != 0:
        return []  # no crontab yet
    return r.stdout.splitlines()


def main() -> int:
    dry = "--dry-run" in sys.argv
    jobs = load_jobs()
    existing = current_crontab()

    # Strip any prior migukstory-hermes lines (idempotent).
    kept = [ln for ln in existing if MARKER not in ln]

    new_lines = []
    report = []
    for j in jobs:
        name = j["name"]
        stem = j["_stem"]
        if not j.get("enabled", True):
            report.append((name, "SKIPPED (enabled: false)", ""))
            continue
        local_cron, note = convert_cron(j["schedule"])
        # run-job.sh resolves ops/hermes/jobs/<stem>.yml — pass the file stem.
        line = f"{local_cron} /bin/bash {RUNNER} {stem} {MARKER}{stem}"
        new_lines.append(line)
        report.append((name, local_cron, note))

    final = kept + ([""] if kept and kept[-1] != "" else []) + \
        ["# ─── migukstory Hermes jobs (managed by install-cron.py) ───"] + new_lines

    crontab_text = "\n".join(final) + "\n"

    print(f"Local timezone: {TZNAME} (UTC{OFFSET_H:+d})\n")
    print("Job schedule (local time):")
    for name, sched, note in report:
        print(f"  {name:38s} {sched:18s} {note}")
    print()

    if dry:
        print("--- DRY RUN — crontab NOT modified. Would install: ---")
        print(crontab_text)
        return 0

    # --out PATH: write the crontab text to a file instead of calling `crontab -`.
    # Useful when `crontab -` is blocked (e.g. macOS TCC on a headless process):
    # the user then runs `crontab <PATH>` themselves in an interactive shell.
    for i, a in enumerate(sys.argv):
        if a == "--out" and i + 1 < len(sys.argv):
            outp = Path(sys.argv[i + 1])
            outp.write_text(crontab_text)
            print(f"✅ Wrote crontab to {outp}")
            print(f"   Install it with:  crontab {outp}")
            return 0

    proc = subprocess.run(["crontab", "-"], input=crontab_text, text=True)
    if proc.returncode != 0:
        print("ERROR: crontab install failed", file=sys.stderr)
        return 1
    print(f"✅ Installed {len(new_lines)} cron entries.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
