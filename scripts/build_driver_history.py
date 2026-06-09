#!/usr/bin/env python3
"""
build_driver_history.py — backfill 2024 + 2025 race-by-race data for every
driver in the 2026 roster. Outputs data/driver-history.json.

WHY THIS EXISTS
---------------
The driver page needs a season-by-season narrative. We have 2026 R1-R6 race
data already (from the Sunday cron). For 2024 and 2025, we fetch from Jolpica
(the same Ergast mirror we use for 2026) and cache locally so the driver
page renders offline.

USAGE
-----
    python3 scripts/build_driver_history.py
    python3 scripts/build_driver_history.py --dry-run   # print plan, no fetch

DATA SHAPES
-----------
Input: data/driver-standings-r6.json (the 22 drivers in 2026)
Output: data/driver-history.json with shape:
{
  "schema_version": 1,
  "generated_utc": "2026-06-09T...",
  "drivers": {
    "<driverId>": {
      "name": "Andrea Kimi Antonelli",
      "nationality": "Italian",
      "history_2024": {
        "races_total": 24,
        "podiums": 0,
        "wins": 0,
        "best_finish": "...",
        "points": 0,
        "races": [
          {"round": 1, "name": "Bahrain Grand Prix", "date": "2024-03-02",
           "qualifying": "P3", "finish": "P9", "team": "Mercedes",
           "time": "+45.123s", "status": "Finished", "points": 2},
          ...
        ]
      },
      "history_2025": {...},
      "season_2026_so_far": {
        "races_total": 6,
        "podiums": 5,
        "wins": 4,
        "best_finish": "P1",
        "points": 156,
        "races": [
          {"round": 1, "name": "Australian Grand Prix", ...},
          ...
        ]
      }
    }
  }
}

JOLPICA / ERGAST API
--------------------
Base URL: https://api.jolpi.ca/ergast/
Per driver per year: /f1/{year}/drivers/{driverId}/results.json
Returns the same shape we already use for 2026 — consistent schema.

DRIVER ID MAPPING
-----------------
Most 2026 driver IDs are stable across years (verified: antonelli, hamilton,
russell, leclerc, piastri, norris, max_verstappen, hadjar, lawson, gasly,
bearman, colapinto, arvid_lindblad, sainz, albon, ocon, bortoleto, alonso,
hulkenberg, bottas, perez, stroll). Rookies in 2026 (hadjar, arvid_lindblad,
bortoleto) had no F1 entry in 2024 — their history_2024 will be empty.

EXIT CODES
----------
0  success
1  Jolpica 5xx that we couldn't retry through
2  rate limit
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DRIVERS_SRC = os.path.join(ROOT, "data", "driver-standings-r6.json")
RACES_DIR = os.path.join(ROOT, "data")
OUT_PATH = os.path.join(ROOT, "data", "driver-history.json")

JOLPICA = "https://api.jolpi.ca/ergast"
TIMEOUT = 30
MAX_RETRIES = 3


def fetch(url):
    """GET URL, retry on 5xx, return parsed JSON."""
    last_err = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with urllib.request.urlopen(url, timeout=TIMEOUT) as r:
                body = r.read().decode("utf-8")
                return json.loads(body)
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code == 429:
                print(f"  rate-limited; sleeping {attempt*2}s", file=sys.stderr)
                time.sleep(attempt * 2)
            elif 500 <= e.code < 600:
                print(f"  HTTP {e.code} attempt {attempt}; sleeping {attempt}s", file=sys.stderr)
                time.sleep(attempt)
            else:
                raise
        except (urllib.error.URLError, json.JSONDecodeError) as e:
            last_err = e
            print(f"  network/parse error attempt {attempt}: {e}", file=sys.stderr)
            time.sleep(attempt)
    raise last_err


def parse_qualifying_results(driver_id, year, data):
    """Convert Jolpica's per-driver-per-year qualifying response to {round: {pos, time}}."""
    out = {}
    for r in data.get("MRData", {}).get("RaceTable", {}).get("Races", []):
        rnd = int(r.get("round", 0))
        for q in r.get("QualifyingResults", []):
            if q.get("Driver", {}).get("driverId") == driver_id:
                out[rnd] = {
                    "position": q.get("position", ""),
                    "time": (q.get("Q3") or q.get("Q2") or q.get("Q1") or ""),
                }
                break
    return out


def merge_qualifying(race_list, qual_map):
    """In-place merge of qualifying data into race records."""
    for r in race_list:
        q = qual_map.get(r["round"])
        if q and r.get("qualifying") is None:
            r["qualifying"] = q


def parse_race_results(driver_id, year, data, qual_map=None):
    """Convert Jolpica's per-driver-per-year response to our history shape.

    qual_map: optional {round: {position, time}} from a separate qualifying fetch,
    merged into race records that lack qualifying data.
    """
    race_table = data.get("MRData", {}).get("RaceTable", {})
    races_raw = race_table.get("Races", [])
    if not races_raw:
        return None
    races = []
    for r in races_raw:
        res = r.get("Results", [{}])[0]
        qual = res.get("Qualifying", {})  # may be absent for older seasons
        races.append({
            "round": int(r.get("round", 0)),
            "name": r.get("raceName", ""),
            "date": r.get("date", ""),
            "qualifying": {
                "position": qual.get("position", ""),
                "time": (qual.get("Q3") or qual.get("Q2") or qual.get("Q1") or ""),
            } if qual else None,
            "finish": {
                "position": res.get("position", ""),
                "positionText": res.get("positionText", ""),
                "time": (res.get("Time") or {}).get("time", ""),
                "status": res.get("status", ""),
                "points": int(res.get("points", 0) or 0),
            },
            "team": (res.get("Constructor") or {}).get("name", ""),
            "laps": int(res.get("laps", 0) or 0),
            "grid": res.get("grid", ""),
        })
    # Sort by round ascending (Jolpica sometimes returns in date order, sometimes not)
    races.sort(key=lambda x: x["round"])
    # Merge qualifying data from a separate endpoint if provided
    if qual_map:
        merge_qualifying(races, qual_map)
    # Compute season aggregates
    podiums = sum(1 for r in races if r["finish"]["positionText"] in ("1", "2", "3"))
    wins = sum(1 for r in races if r["finish"]["positionText"] == "1")
    points = sum(r["finish"]["points"] for r in races)
    # Best finish (lowest position)
    finished = [r for r in races if r["finish"]["status"] == "Finished"]
    if finished:
        best = min(finished, key=lambda r: int(r["finish"]["position"]) if r["finish"]["position"].isdigit() else 99)
        best_finish = f"P{best['finish']['position']}"
    else:
        best_finish = "DNF"
    return {
        "races_total": len(races),
        "podiums": podiums,
        "wins": wins,
        "best_finish": best_finish,
        "points": points,
        "races": races,
    }


def build_2026_from_local(driver_id, driver_name):
    """Build the 2026-so-far section from the local race files. No fetch."""
    races = []
    for fn in sorted(os.listdir(RACES_DIR)):
        if not (fn.startswith("r") and "-" in fn and fn.endswith(".json")):
            continue
        if "qualifying" in fn:
            continue
        path = os.path.join(RACES_DIR, fn)
        with open(path) as f:
            data = json.load(f)
        race_arr = data.get("MRData", {}).get("RaceTable", {}).get("Races", [])
        if not race_arr:
            continue
        race = race_arr[0]
        # Find this driver in the results
        driver_res = None
        for r in race.get("Results", []):
            if r.get("Driver", {}).get("driverId") == driver_id:
                driver_res = r
                break
        if not driver_res:
            continue
        # Try to load qualifying
        qpath = path.replace(".json", "-qualifying.json")
        qual = None
        if os.path.exists(qpath):
            try:
                qdata = json.load(open(qpath))
                for q in qdata["MRData"]["RaceTable"]["Races"][0].get("QualifyingResults", []):
                    if q.get("Driver", {}).get("driverId") == driver_id:
                        qual = {
                            "position": q.get("position", ""),
                            "time": (q.get("Q3") or q.get("Q2") or q.get("Q1") or ""),
                        }
                        break
            except (json.JSONDecodeError, KeyError, IndexError):
                pass
        races.append({
            "round": int(race.get("round", 0)),
            "name": race.get("raceName", ""),
            "date": race.get("date", ""),
            "qualifying": qual,
            "finish": {
                "position": driver_res.get("position", ""),
                "positionText": driver_res.get("positionText", ""),
                "time": (driver_res.get("Time") or {}).get("time", ""),
                "status": driver_res.get("status", ""),
                "points": int(driver_res.get("points", 0) or 0),
            },
            "team": (driver_res.get("Constructor") or {}).get("name", ""),
            "laps": int(driver_res.get("laps", 0) or 0),
            "grid": driver_res.get("grid", ""),
        })
    races.sort(key=lambda x: x["round"])
    if not races:
        return None
    podiums = sum(1 for r in races if r["finish"]["positionText"] in ("1", "2", "3"))
    wins = sum(1 for r in races if r["finish"]["positionText"] == "1")
    points = sum(r["finish"]["points"] for r in races)
    finished = [r for r in races if r["finish"]["status"] == "Finished"]
    if finished:
        best = min(finished, key=lambda r: int(r["finish"]["position"]) if r["finish"]["position"].isdigit() else 99)
        best_finish = f"P{best['finish']['position']}"
    else:
        best_finish = "DNF"
    return {
        "races_total": len(races),
        "podiums": podiums,
        "wins": wins,
        "best_finish": best_finish,
        "points": points,
        "races": races,
    }


def main():
    p = argparse.ArgumentParser(description="Backfill 2024 + 2025 driver race data")
    p.add_argument("--dry-run", action="store_true", help="print plan, no fetch")
    args = p.parse_args()

    with open(DRIVERS_SRC) as f:
        standings = json.load(f)
    drivers_2026 = standings["MRData"]["StandingsTable"]["StandingsLists"][0]["DriverStandings"]
    print(f"[plan] {len(drivers_2026)} drivers × 2 years (2024, 2025) × 2 endpoints (results + qualifying) = "
          f"{len(drivers_2026) * 4} API calls + {len(drivers_2026)} local 2026 builds")
    if args.dry_run:
        return 0

    out = {
        "schema_version": 1,
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": "Jolpica/Ergast API + local 2026 race files",
        "drivers": {},
    }

    for d in drivers_2026:
        drv = d["Driver"]
        driver_id = drv["driverId"]
        name = f"{drv['givenName']} {drv['familyName']}"
        nationality = drv.get("nationality", "")
        print(f"\n[{driver_id}] {name} ({nationality})")

        driver_entry: dict = {
            "name": name,
            "nationality": nationality,
            "permanent_number": drv.get("permanentNumber", ""),
        }

        # 2024 + 2025 from Jolpica (results + qualifying)
        for year in (2024, 2025):
            url_r = f"{JOLPICA}/f1/{year}/drivers/{driver_id}/results.json"
            url_q = f"{JOLPICA}/f1/{year}/drivers/{driver_id}/qualifying.json"
            print(f"  → {year}: GET results + qualifying")
            try:
                data_r = fetch(url_r)
                data_q = fetch(url_q)
            except Exception as exc:  # noqa: BLE001
                print(f"  ⚠️ {year} fetch failed: {exc}")
                driver_entry[f"history_{year}"] = None
                continue
            qual_map = parse_qualifying_results(driver_id, year, data_q)
            hist = parse_race_results(driver_id, year, data_r, qual_map=qual_map)
            driver_entry[f"history_{year}"] = hist
            if hist:
                qual_pct = 100 * sum(1 for r in hist["races"] if r.get("qualifying")) // max(1, hist["races_total"])
                print(f"    {hist['races_total']} races, {hist['wins']}W/{hist['podiums']}P, "
                      f"{hist['points']} pts, best {hist['best_finish']}, qual coverage {qual_pct}%")
            else:
                print(f"    no F1 races in {year}")
            time.sleep(0.6)  # gentle rate-limiting (2 calls per driver-year)

        # 2026 from local race files (no fetch)
        s26 = build_2026_from_local(driver_id, name)
        driver_entry["season_2026_so_far"] = s26
        if s26:
            print(f"  → 2026 (local): {s26['races_total']} races, {s26['wins']}W/{s26['podiums']}P, "
                  f"{s26['points']} pts")

        out["drivers"][driver_id] = driver_entry

    with open(OUT_PATH, "w") as f:
        json.dump(out, f, indent=2)
    print(f"\n[ok] wrote {OUT_PATH} ({os.path.getsize(OUT_PATH)} bytes)")
    print(f"[ok] {len(out['drivers'])} drivers, "
          f"{sum(1 for d in out['drivers'].values() if d.get('history_2024'))} have 2024 data, "
          f"{sum(1 for d in out['drivers'].values() if d.get('history_2025'))} have 2025 data, "
          f"{sum(1 for d in out['drivers'].values() if d.get('season_2026_so_far'))} have 2026 data")
    return 0


if __name__ == "__main__":
    sys.exit(main())
