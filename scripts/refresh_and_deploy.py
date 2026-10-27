#!/usr/bin/env python3
"""
F1 2026 data refresh + team-specs scrape + Pages deploy hook (2026-06-10)

Wraps the existing data-refresh scripts with a team-specs scrape and a
git commit + push step so the public Cloudflare Pages URL gets rebuilt
with fresh data. The Tailscale URL (http://100.91.143.50:8081) is
unaffected; the public URL (https://f1-2026-viewer.pages.dev) gets the new
data within ~60s of push.

Flow (each step only runs if the previous succeeded):
  1. update_f1_data.py     — refreshes latest race results, qualifying,
                              standings, season summary
  2. build_issue_data.py   — derives part-changes.json + car-issues-dnf.json
                              from the on-disk race JSONs
  3. derive_pace.py        — recomputes pace-dashboard.json
  4. build_team_specs.py   — fetches public 2026 F1 press articles, calls
                              the LLM (minimax-m3 via ollama-cloud) to
                              extract each team's specific technical
                              specification for each car part, writes
                              data/team-part-specs.json (consumed by the
                              Explore-the-Car "Latest design" section)
  5. git add data/ (only data/ — never HTML/JS/CSS)
  6. If there are changes, commit + push; otherwise skip
  7. Always exit 0 if the data steps succeeded

The cron job ID `87ed139da066` is configured to run THIS script. See
`jobs.json` in `~/.hermes/cron/`. Previously the job pointed at
update_f1_data.py directly; the one-line swap to this wrapper was
documented but not yet applied (waiting for Sir's go).

Why this lives outside update_f1_data.py:
  - Keeps the data-refresh logic pure and unit-testable
  - The git step is purely a deploy concern, not a data concern
  - The team-specs step is a content concern, not a race-data concern
  - If we ever switch off Pages (e.g. back to Tunnel), only this file changes
"""

import subprocess
import sys
import os
from pathlib import Path
from datetime import datetime, timezone

PROJECT_ROOT = Path("/root/.hermes/workspace/projects/f1-2026-viewer")
DATA_DIR = PROJECT_ROOT / "data"
SCRIPTS_DIR = PROJECT_ROOT / "scripts"

# Ordered steps. Split per the 2026-10-27 contract in the sports-trackers
# skill: DATA_STEPS abort the pipeline on failure (race-data freshness is the
# product); build_team_specs is ADVISORY — it calls the LLM (minimax via
# ollama-cloud), is slow, can fail on billing/rate errors, and must NEVER
# block the data push. build_team_specs.py replaced build_team_quotes.py
# on 2026-06-10 — specs (what the team actually did) replaced quotes.
DATA_STEPS = [
    ("update_f1_data",   "scripts/update_f1_data.py"),
    ("build_issue_data", "scripts/build_issue_data.py"),
    ("derive_pace",      "scripts/derive_pace.py"),
]
ADVISORY_STEPS = [
    # (name, path, timeout_s) — LLM step needs minutes, not the old 180s cap
    ("build_team_specs", "scripts/build_team_specs.py", 900),
]


def run_script(step_name: str, rel_path: str, timeout: int = 300) -> int:
    """Run one step of the pipeline. Returns its exit code (124 = timeout)."""
    script = PROJECT_ROOT / rel_path
    print(f"[deploy] {datetime.now(timezone.utc).isoformat()} step={step_name} running {script.name}", flush=True)
    try:
        res = subprocess.run(
            [sys.executable, str(script)],
            cwd=PROJECT_ROOT,
            capture_output=False,  # let stdout flow to cron log
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        # Never let a step's timeout crash the runner itself (the 2026-10-27
        # run died here with an unhandled TimeoutExpired and skipped the push).
        print(f"[deploy] step={step_name} TIMEOUT after {timeout}s — treated as failure", flush=True)
        return 124
    print(f"[deploy] step={step_name} exit={res.returncode}", flush=True)
    return res.returncode


def git_push_data_changes() -> tuple[int, str]:
    """Stage data/, commit if anything changed, push to origin. Returns (rc, message)."""
    # Add only the data directory — never stage HTML/JS/CSS changes
    # (those are Sir's intentional changes, not auto-deploys)
    res = subprocess.run(
        ["git", "add", "data/"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )
    if res.returncode != 0:
        return res.returncode, f"git add failed: {res.stderr}"

    # Check if there are any staged changes
    diff_res = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )
    if not diff_res.stdout.strip():
        return 0, "no data changes; nothing to push"

    # Commit with a deterministic message
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    commit_msg = f"data: refresh F1 race data — {timestamp}"
    commit_res = subprocess.run(
        ["git", "commit", "-m", commit_msg],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )
    if commit_res.returncode != 0:
        return commit_res.returncode, f"git commit failed: {commit_res.stderr}"

    # Push — the only network call in this script. NOTE: F1 repo branch is
    # MAIN (the lemans-2026-viewer repo is the master one — verified 2026-10-27;
    # don't overgeneralize between the two viewer repos).
    push_res = subprocess.run(
        ["git", "push", "origin", "main"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=60,
    )
    if push_res.returncode != 0:
        return push_res.returncode, f"git push failed: {push_res.stderr}"

    return 0, f"pushed: {commit_msg}"


def main() -> int:
    # Data steps: race-data freshness is the product — abort on failure.
    for step_name, rel_path in DATA_STEPS:
        rc = run_script(step_name, rel_path)
        if rc != 0:
            print(f"[deploy] {step_name} FAILED with exit code {rc}", flush=True)
            return rc

    # Advisory step: team-specs scrape (LLM). Slow / can fail on billing,
    # rate limits or slow models — log and CONTINUE to the push. It was
    # moved after the data steps for exactly this reason.
    for step_name, rel_path, step_timeout in ADVISORY_STEPS:
        rc = run_script(step_name, rel_path, timeout=step_timeout)
        if rc != 0:
            print(f"[deploy] WARNING: {step_name} failed (rc={rc}) — advisory step, "
                  f"continuing to push; specs refresh again next run", flush=True)

    # Step 5: git push (triggers Pages rebuild)
    print("[deploy] data pipeline ok; checking for git changes to push", flush=True)
    push_rc, push_msg = git_push_data_changes()
    print(f"[deploy] git push: rc={push_rc} msg={push_msg}", flush=True)

    # Even if push failed, the local data is fresh and Tailscale URL serves it.
    # Cron job's silent-on-success contract means we exit 0 if the data steps
    # worked. Pages will just be a few hours stale, which is acceptable.
    if push_rc != 0:
        print(f"[deploy] WARNING: push failed but data is local-fresh", flush=True)
        # Don't fail the cron — Tailscale URL still works, public URL will catch up
        # when Sir manually pushes later.

    return 0


if __name__ == "__main__":
    sys.exit(main())
