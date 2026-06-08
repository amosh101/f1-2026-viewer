#!/usr/bin/env python3
"""
build_issue_data.py — derive car-issues + part-changes Datasets from on-disk
race JSONs.

Outputs:
  data/car-issues-dnf.json     — mechanical/electrical DNFs, grouped by team
  data/part-changes.json       — placeholder; populated manually from
                                 media scraping (see SCRAPE-NOTES.md)

Mechanical/electrical statuses that count as "car issues" (case-insensitive):
  Power unit, Engine, Gearbox, Transmission, Clutch, Hydraulics, Electrical,
  Oil leak, Water pressure, Oil pressure, Cooling, Radiator, Suspension,
  Brakes, Wheel, Tyre, Puncture, Exhaust, Turbo, MGU, Battery, ERS,
  Power loss, Overheating, Throttle, Fuel system, Fuel pressure, Water leak,
  Oil line, Driveshaft, CV joint, Half-shaft, Driveshaft

Excluded: 'Finished', 'Collision', 'Damage', '+N Lap', 'Disqualified',
'Withdrew', 'Did not start', 'Did not qualify', 'Not classified', '107%',
'Accident', 'Spun off', 'Fatal accident'.

Run:
  python3 scripts/build_issue_data.py
"""

from __future__ import annotations

import json
import logging
import re
import sys
from collections import defaultdict
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
LOG_FILE = Path(__file__).resolve().parent / "build_issue_data.log"

# Words that indicate a mechanical/electrical DNF (not driver error, not collision).
MECHANICAL_KEYWORDS = [
    "power unit", "engine", "gearbox", "transmission", "clutch",
    "hydraul", "electrical", "electr", "battery", "ers",
    "mgu", "turbo", "exhaust", "cool", "radiator", "overheat",
    "oil", "water", "fuel", "throttle", "brake", "suspension",
    "wheel", "tyre", "tire", "puncture", "driveshaft", "half-shaft",
    "half shaft", "cv joint", "power loss", "leak", "pressure",
]

EXCLUDED_STATUSES = {
    "Finished",
    "Collision",
    "Damage",
    "Withdrew",
    "Did not start",
    "Did not qualify",
    "Not classified",
    "Disqualified",
    "Accident",
    "Spun off",
    "Fatal accident",
}


def is_mechanical(status: str) -> bool:
    s = (status or "").strip()
    if s in EXCLUDED_STATUSES:
        return False
    if s.startswith("+") and "Lap" in s:
        return False
    if "107%" in s:
        return False
    low = s.lower()
    return any(k in low for k in MECHANICAL_KEYWORDS)


def setup_logging() -> logging.Logger:
    logger = logging.getLogger("build_issue_data")
    logger.setLevel(logging.INFO)
    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
    )
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    logger.addHandler(sh)
    try:
        fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
        fh.setFormatter(fmt)
        logger.addHandler(fh)
    except OSError as e:
        logger.warning("could not open log file %s: %s", LOG_FILE, e)
    return logger


def main() -> int:
    logger = setup_logging()
    logger.info("=== build_issue_data.py start ===")

    # Find all per-race files
    race_files = sorted(
        p for p in DATA_DIR.glob("r[1-9]*.json")
        if "qualifying" not in p.name
        and "standings" not in p.name
        and "summary" not in p.name
    )
    if not race_files:
        logger.error("no race files found in %s", DATA_DIR)
        return 1
    logger.info("found %d race files", len(race_files))

    # Round slug -> (round, name, date)
    round_meta: dict[str, tuple[int, str, str]] = {}

    # team id -> list of issues
    issues_by_team: dict[str, list[dict]] = defaultdict(list)

    for path in race_files:
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            logger.warning("skip %s: %s", path.name, e)
            continue
        races = doc.get("MRData", {}).get("RaceTable", {}).get("Races", [])
        if not races:
            continue
        race = races[0]
        rnd = int(race["round"])
        round_meta[f"r{rnd}"] = (rnd, race.get("raceName", ""), race.get("date", ""))

        for r in race.get("Results", []):
            status = r.get("status", "")
            if not is_mechanical(status):
                continue
            team_id = r.get("Constructor", {}).get("constructorId", "unknown")
            issues_by_team[team_id].append(
                {
                    "round": rnd,
                    "race": race.get("raceName", ""),
                    "date": race.get("date", ""),
                    "driver_id": r.get("Driver", {}).get("driverId"),
                    "driver_name": (
                        r.get("Driver", {}).get("givenName", "")
                        + " "
                        + r.get("Driver", {}).get("familyName", "")
                    ).strip(),
                    "permanent_number": r.get("Driver", {}).get("permanentNumber"),
                    "car_number": r.get("number"),
                    "status": status,
                    "laps_completed": r.get("laps"),
                    "classification_position": r.get("positionText"),
                }
            )

    # Build output shape
    out = {
        "generated_utc": None,  # filled in below
        "methodology": (
            "Mechanical/electrical DNFs derived from official race classification "
            "status field. Excludes: Finished, Collision, Damage, Accident, Spun off, "
            "Withdrew, Did not start, +N Lap, 107% rule, Disqualified. "
            "Source: Jolpica Ergast mirror (F1 official)."
        ),
        "rounds_covered": [
            {"round": meta[0], "name": meta[1], "date": meta[2]}
            for key, meta in sorted(round_meta.items(), key=lambda kv: kv[1][0])
        ],
        "teams": [],
    }
    import datetime as dt
    out["generated_utc"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")

    # Stable team ordering: by DNF count desc, then team id
    teams_sorted = sorted(
        issues_by_team.items(), key=lambda kv: (-len(kv[1]), kv[0])
    )
    for team_id, issues in teams_sorted:
        out["teams"].append(
            {
                "team_id": team_id,
                "issue_count": len(issues),
                "issues": sorted(issues, key=lambda i: (i["round"], i["car_number"] or "")),
            }
        )

    out_path = DATA_DIR / "car-issues-dnf.json"
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    logger.info(
        "wrote %s: %d teams, %d total issues",
        out_path.name,
        len(out["teams"]),
        sum(t["issue_count"] for t in out["teams"]),
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
