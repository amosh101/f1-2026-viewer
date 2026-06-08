#!/usr/bin/env python3
"""
update_f1_data.py — refresh F1 2026 data for the F1 2026 viewer.

Refreshes on every run:
  - Latest round + last 3 rounds (results + qualifying)
  - Driver + constructor standings
  - data/season-summary.json (podium + pole for each completed round)

Saves to ./data/. Atomic writes (tmp + rename) so the static server
never reads partial JSON. No git operations.

Source: Jolpica Ergast mirror at api.jolpi.ca/ergast (free, no key).
Schedule: Sunday 23:00 CAT (= 21:00 UTC) via cron.

Run manually:
    python3 scripts/update_f1_data.py
    python3 scripts/update_f1_data.py --dry-run   # log only, no writes
    python3 scripts/update_f1_data.py --verbose   # print all API calls

Exit codes:
    0 — success (or no-op; nothing changed)
    1 — network/HTTP error
    2 — JSON parse error
    3 — filesystem error
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

# ---------- config ----------
API_BASE = "https://api.jolpi.ca/ergast"
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
LOG_FILE = Path(__file__).resolve().parent / "update_f1_data.log"
SEASON = 2026
TIMEOUT = 20  # seconds per HTTP request
USER_AGENT = "f1-2026-viewer-cron/1.0 (+amosh101)"
AMENDMENT_WINDOW = 3  # refresh latest N rounds (covers result amendments)

# Round slug map (kept in code because slugs are used in filenames).
# Mirrors what's already on disk: r1-australia, r2-china, r3-japan, etc.
# The Ergast API returns adjective forms ("Australian Grand Prix") for some
# races, but our on-disk filenames use the country/location noun. Override
# the demonym to the noun for the 2026 calendar.
_RACE_NAME_TO_SLUG: dict[str, str] = {
    "Australian Grand Prix": "australia",
    "Chinese Grand Prix": "china",
    "Japanese Grand Prix": "japan",
    "Miami Grand Prix": "miami",
    "Canadian Grand Prix": "canada",
    "Monaco Grand Prix": "monaco",
    "Barcelona Grand Prix": "barcelona",
    "Austrian Grand Prix": "austria",
    "British Grand Prix": "britain",
    "Belgian Grand Prix": "belgium",
    "Hungarian Grand Prix": "hungary",
    "Dutch Grand Prix": "netherlands",
    "Italian Grand Prix": "italy",
    "Spanish Grand Prix": "spain",
    "Azerbaijan Grand Prix": "azerbaijan",
    "Singapore Grand Prix": "singapore",
    "United States Grand Prix": "united-states",
    "Mexico City Grand Prix": "mexico",
    "Brazilian Grand Prix": "brazil",
    "Las Vegas Grand Prix": "las-vegas",
    "Qatar Grand Prix": "qatar",
    "Abu Dhabi Grand Prix": "abu-dhabi",
}


def slug_for(race_name: str) -> str:
    if race_name in _RACE_NAME_TO_SLUG:
        return _RACE_NAME_TO_SLUG[race_name]
    # Fallback: strip "Grand Prix", lowercase, hyphenate.
    name = re.sub(r"\s*Grand Prix\s*$", "", race_name).strip()
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


# ---------- logging ----------
def setup_logging(verbose: bool) -> logging.Logger:
    logger = logging.getLogger("update_f1_data")
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
    )
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    logger.addHandler(sh)
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
        fh.setFormatter(fmt)
        logger.addHandler(fh)
    except OSError as e:
        logger.warning("could not open log file %s: %s", LOG_FILE, e)
    return logger


# ---------- http ----------
def http_get_json(url: str, logger: logging.Logger) -> dict[str, Any]:
    """GET a URL and return parsed JSON. Retries on 5xx / network errors."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    last_err: Exception | None = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                body = resp.read()
                return json.loads(body.decode("utf-8"))
        except urllib.error.HTTPError as e:
            if 500 <= e.code < 600 and attempt < 2:
                logger.warning("HTTP %s from %s, retrying in 2s", e.code, url)
                time.sleep(2)
                last_err = e
                continue
            raise
        except (urllib.error.URLError, TimeoutError) as e:
            last_err = e
            if attempt < 2:
                logger.warning("network error %s, retrying in 2s", e)
                time.sleep(2)
                continue
            raise
    raise RuntimeError(f"unreachable: {url} ({last_err})")


# ---------- atomic write ----------
def write_json_atomic(path: Path, obj: Any, logger: logging.Logger) -> bool:
    """Write JSON to path atomically. Returns True if file content changed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    new_bytes = json.dumps(obj, indent=2, ensure_ascii=False).encode("utf-8")
    new_bytes += b"\n"  # POSIX text-file nicety
    if path.exists():
        try:
            old_bytes = path.read_bytes()
            if old_bytes == new_bytes:
                logger.debug("unchanged: %s", path.name)
                return False
        except OSError as e:
            logger.warning("read failed for %s: %s — writing anyway", path, e)
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp.write_bytes(new_bytes)
        os.replace(tmp, path)
    except OSError as e:
        logger.error("write failed for %s: %s", path, e)
        raise
    logger.info("wrote %s (%d bytes)", path.name, len(new_bytes))
    return True


# ---------- main work ----------
def fetch_season(logger: logging.Logger) -> list[dict[str, Any]]:
    """Get the 2026 season schedule."""
    url = f"{API_BASE}/f1/{SEASON}.json"
    logger.debug("GET %s", url)
    data = http_get_json(url, logger)
    races = data["MRData"]["RaceTable"]["Races"]
    logger.info("season has %d rounds scheduled", len(races))
    return races


def is_completed(race: dict[str, Any], today: dt.date) -> bool:
    """A race counts as 'completed' if its date is today or earlier.

    The cron fires Sunday 23:00 CAT; race day for European GPs is also Sunday,
    so on most weeks the same-day race will already be in the books. The +1 day
    buffer (caller's responsibility) is intentionally not here to avoid pulling
    in races that haven't actually started.
    """
    race_date = dt.date.fromisoformat(race["date"])
    return race_date <= today


def fetch_rounds_to_refresh(
    races: list[dict[str, Any]],
    today: dt.date,
    logger: logging.Logger,
) -> list[dict[str, Any]]:
    """Pick which rounds to refresh: latest N completed rounds (amendment window)."""
    completed = [r for r in races if is_completed(r, today)]
    if not completed:
        return []
    # Sort by round number (race order), take last AMENDMENT_WINDOW
    completed_sorted = sorted(completed, key=lambda r: int(r["round"]))
    selected = completed_sorted[-AMENDMENT_WINDOW:]
    logger.info(
        "refreshing %d of %d completed rounds: R%s .. R%s",
        len(selected),
        len(completed),
        selected[0]["round"],
        selected[-1]["round"],
    )
    return selected


def fetch_round_files(
    race: dict[str, Any], logger: logging.Logger, dry_run: bool
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Fetch results + qualifying for one round. Returns (results, qualifying) or Nones."""
    rnd = race["round"]
    slug = slug_for(race["raceName"])

    # Results
    results_url = f"{API_BASE}/f1/{SEASON}/{rnd}/results.json"
    logger.debug("GET %s", results_url)
    try:
        results = http_get_json(results_url, logger)
    except Exception as e:
        logger.error("results fetch failed for R%s: %s", rnd, e)
        return None, None
    if not dry_run:
        path = DATA_DIR / f"r{rnd}-{slug}.json"
        write_json_atomic(path, results, logger)

    # Qualifying
    try:
        qual_url = f"{API_BASE}/f1/{SEASON}/{rnd}/qualifying.json"
        logger.debug("GET %s", qual_url)
        qualifying = http_get_json(qual_url, logger)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            logger.info("no qualifying yet for R%s (sprint weekend?)", rnd)
            qualifying = None
        else:
            logger.error("qualifying fetch failed for R%s: %s", rnd, e)
            qualifying = None
    except Exception as e:
        logger.error("qualifying fetch failed for R%s: %s", rnd, e)
        qualifying = None

    if qualifying and not dry_run:
        path = DATA_DIR / f"r{rnd}-{slug}-qualifying.json"
        write_json_atomic(path, qualifying, logger)

    return results, qualifying


def fetch_standings(logger: logging.Logger, dry_run: bool, latest_round: str) -> None:
    """Refresh driver + constructor standings as of latest_round."""
    for kind, fname in (
        ("driverstandings", f"driver-standings-r{latest_round}.json"),
        ("constructorstandings", f"constructor-standings-r{latest_round}.json"),
    ):
        url = f"{API_BASE}/f1/{SEASON}/{kind}.json"
        logger.debug("GET %s", url)
        try:
            data = http_get_json(url, logger)
        except Exception as e:
            logger.error("%s fetch failed: %s", kind, e)
            continue
        if not dry_run:
            write_json_atomic(DATA_DIR / fname, data, logger)


def build_season_summary(races: list[dict[str, Any]], today: dt.date) -> dict[str, Any]:
    """Build season-summary.json from per-race files on disk.

    Schema (one entry per completed round):
        {
          "r1": {
            "round": 1,
            "name": "Australian Grand Prix",
            "date": "2026-03-08",
            "circuit": "Albert Park Grand Prix Circuit",
            "podium": [ {pos, driver, team}, ... ],
            "pole":   {driver, team, time} | null,
            "fastest_lap": {driver, team, time} | null,
            "winner_time": "1:30:00.000" | null
          },
          ...
        }
    """
    summary: dict[str, Any] = {}
    for race in races:
        if not is_completed(race, today):
            continue
        rnd = race["round"]
        slug = slug_for(race["raceName"])
        results_path = DATA_DIR / f"r{rnd}-{slug}.json"
        qual_path = DATA_DIR / f"r{rnd}-{slug}-qualifying.json"
        if not results_path.exists():
            logger_skip = "no results file for R%s (skipping in summary)"
            continue
        try:
            results_doc = json.loads(results_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        races_arr = results_doc.get("MRData", {}).get("RaceTable", {}).get("Races", [])
        if not races_arr:
            continue
        race_doc = races_arr[0]
        results_list = race_doc.get("Results", [])

        podium: list[dict[str, Any]] = []
        for r in results_list[:3]:
            podium.append(
                {
                    "pos": int(r["position"]),
                    "driver": r["Driver"]["familyName"],
                    "team": r["Constructor"]["name"],
                }
            )

        winner_time = None
        for r in results_list:
            if r.get("position") == "1":
                t = r.get("Time", {}).get("time")
                if t:
                    winner_time = t
                break

        fastest_lap = None
        for r in results_list:
            fl = r.get("FastestLap", {})
            if fl and fl.get("rank") == "1":
                fastest_lap = {
                    "driver": r["Driver"]["familyName"],
                    "team": r["Constructor"]["name"],
                    "time": fl.get("Time", {}).get("time"),
                    "lap": fl.get("lap"),
                }
                break

        pole = None
        if qual_path.exists():
            try:
                qual_doc = json.loads(qual_path.read_text(encoding="utf-8"))
                qual_results = (
                    qual_doc.get("MRData", {})
                    .get("RaceTable", {})
                    .get("Races", [{}])[0]
                    .get("QualifyingResults", [])
                )
                if qual_results:
                    q1 = qual_results[0]
                    pole = {
                        "driver": q1["Driver"]["familyName"],
                        "team": q1["Constructor"]["name"],
                        "time": q1.get("Q3") or q1.get("Q2") or q1.get("Q1"),
                    }
            except (OSError, json.JSONDecodeError):
                pass

        summary[f"r{rnd}"] = {
            "round": int(rnd),
            "name": race_doc.get("raceName", race["raceName"]),
            "date": race_doc.get("date", race["date"]),
            "circuit": race_doc.get("Circuit", {}).get("circuitName"),
            "podium": podium,
            "pole": pole,
            "fastest_lap": fastest_lap,
            "winner_time": winner_time,
        }
    return summary


# ---------- entrypoint ----------
def main() -> int:
    desc = (__doc__ or "").splitlines()[1] if __doc__ else "Update F1 2026 data."
    parser = argparse.ArgumentParser(description=desc)
    parser.add_argument("--dry-run", action="store_true", help="log only, no writes")
    parser.add_argument("--verbose", action="store_true", help="debug-level logging")
    args = parser.parse_args()

    logger = setup_logging(args.verbose)
    logger.info("=== update_f1_data.py start (dry_run=%s) ===", args.dry_run)

    try:
        races = fetch_season(logger)
    except Exception as e:
        logger.error("could not fetch season schedule: %s", e)
        return 1

    today = dt.datetime.now(dt.timezone.utc).date() + dt.timedelta(days=0)
    selected = fetch_rounds_to_refresh(races, today, logger)

    if not selected:
        logger.info("no completed rounds to refresh — nothing to do")
        return 0

    latest_round = selected[-1]["round"]
    written = 0
    for race in selected:
        try:
            results, qual = fetch_round_files(race, logger, args.dry_run)
            if results is None:
                continue
            written += 1
        except Exception as e:
            logger.error("R%s failed: %s", race["round"], e)
            continue

    if not args.dry_run:
        try:
            fetch_standings(logger, args.dry_run, latest_round)
        except Exception as e:
            logger.error("standings fetch failed: %s", e)

        # Rebuild season-summary from ALL per-race files on disk
        # (not just the 3 we refreshed in the amendment window — we want
        # the full completed-season record, including rounds 1..latest.)
        try:
            summary = build_season_summary(races, today)
            if summary:
                write_json_atomic(DATA_DIR / "season-summary.json", summary, logger)
            else:
                logger.warning("season summary would be empty — keeping existing")
        except Exception as e:
            logger.error("season-summary build failed: %s", e)
            return 3

        # Write a tiny pointer the home screen can read to find the latest
        # standings file without needing to glob.
        try:
            latest_pointer = {
                "round": int(latest_round),
                "updated_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                "rounds_completed": sum(
                    1 for r in races if is_completed(r, today)
                ),
            }
            write_json_atomic(DATA_DIR / "latest.json", latest_pointer, logger)
        except Exception as e:
            logger.error("latest.json write failed: %s", e)

        # Re-derive car-issues-dnf.json from the per-race files so it stays
        # fresh as new races are added. The script is a sibling in scripts/.
        try:
            import subprocess
            res = subprocess.run(
                [sys.executable, str(Path(__file__).parent / "build_issue_data.py")],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if res.returncode == 0:
                logger.info("build_issue_data.py: ok")
            else:
                logger.error(
                    "build_issue_data.py failed: rc=%s stderr=%s",
                    res.returncode,
                    res.stderr[-500:] if res.stderr else "",
                )
        except Exception as e:
            logger.error("could not invoke build_issue_data.py: %s", e)

    logger.info("=== update_f1_data.py done (%d rounds updated) ===", written)
    return 0


if __name__ == "__main__":
    sys.exit(main())
