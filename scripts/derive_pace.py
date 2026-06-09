#!/usr/bin/env python3
"""
derive_pace.py — compute per-team pace statistics from on-disk race +
qualifying JSONs. Engineer-grade competitive intelligence.

Outputs:
  data/pace-dashboard.json — every team, every round:
    {
      "generated_utc": "...",
      "methodology": "...",
      "rounds_covered": [{round, name, date, laps}, ...],
      "teams": [{
        "team_id": "mercedes",
        "season": {
          "races": 6,                              # races started
          "wins": 4,                               # P1 finishes
          "podiums": 8,                            # top-3 finishes
          "best_qual": "1:12.051",                 # best Q3 (or Q2 / Q1) all season
          "best_lap": "1:13.481",                  # best fastest-lap all season
          "avg_pace_delta_to_winner_s": 0.4,       # average gap across finishes
          "median_position": 2                     # typical finishing position
        },
        "by_round": [{
          "round": 6,
          "race": "Monaco Grand Prix",
          "date": "2026-06-07",
          "drivers": [
            {"name": "Antonelli", "num": 12, "pos": 1, "grid": 1,
             "best_lap": "1:13.481", "best_lap_rank": 1,
             "q_best": "1:12.051", "q_pos": 1, "q_gap_to_pole_s": 0.0,
             "pace_avg_s": 110.4, "pace_delta_to_winner_s": 0.0,
             "laps": 78, "status": "Finished"},
            ...
          ]
        }, ...]
      }, ...]
    }

The pace_avg_s = total_race_time / laps (computed from winner's Time.millis
and laps_completed). Other finishers' pace_avg_s derived from
(winner_time - gap_to_winner) / laps_completed. Non-finishers carry no
pace and a status flag.

Methodology caveats surfaced on the page:
  - Race average pace mixes tyre stints; stint-level analysis needs
    per-lap data (OpenF1 telemetry, currently unavailable for 2026).
  - DNFs are excluded from pace computation.
  - A "+1 Lap" finisher is treated as finished but the gap is a
    lap delta, not a time delta — we surface the raw status string.

Run: python3 scripts/derive_pace.py
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
LOG_FILE = Path(__file__).resolve().parent / "derive_pace.log"

# ---------- time parsing ----------
_TIME_RE = re.compile(r"^(?:(\+)?(\d+):)?(\d{1,2}):(\d{1,2})\.(\d{1,3})$")
def parse_time(s: str | None) -> float | None:
    """Parse an F1 time string to seconds. Handles:
        "2:23:31.243"   (winner time, h:mm:ss.mmm)
        "+6.271"        (gap, s.mmm)
        "+1:23.456"     (gap, m:ss.mmm)
        "1:13.481"      (lap, m:ss.mmm)
       Returns None if the string is None or unparseable."""
    if not s:
        return None
    s = s.strip()
    if s.startswith("+"):
        # Gap: optional minutes
        m = re.match(r"^\+(?:(\d+):)?(\d{1,2})\.(\d{1,3})$", s)
        if m:
            mins = int(m.group(1) or 0)
            secs = int(m.group(2))
            ms = int(m.group(3).ljust(3, "0")[:3])
            return mins * 60 + secs + ms / 1000
        return None
    m = _TIME_RE.match(s)
    if not m:
        return None
    sign = -1 if m.group(1) == "-" else 1
    hours = int(m.group(2) or 0)
    mins = int(m.group(3))
    secs = int(m.group(4))
    ms_field = m.group(5)
    ms = int(ms_field.ljust(3, "0")[:3])
    return sign * (hours * 3600 + mins * 60 + secs + ms / 1000)


def fmt_lap(seconds: float | None) -> str | None:
    if seconds is None:
        return None
    if seconds < 0:
        return None
    m = int(seconds // 60)
    s = seconds - m * 60
    return f"{m}:{s:06.3f}"


# ---------- logging ----------
def setup_logging() -> logging.Logger:
    logger = logging.getLogger("derive_pace")
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


# ---------- discovery ----------
def race_files() -> list[Path]:
    return sorted(
        p for p in DATA_DIR.glob("r[1-9]*.json")
        if "qualifying" not in p.name
        and "standings" not in p.name
        and "summary" not in p.name
    )


def load_json(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


# ---------- per-round computation ----------
def pace_for_round(race_doc: dict[str, Any], qual_doc: dict[str, Any] | None) -> dict[str, Any]:
    race = race_doc["MRData"]["RaceTable"]["Races"][0]
    rnd = int(race["round"])
    results = race.get("Results", [])

    # Find winner: position == "1"
    winner = next((r for r in results if r.get("position") == "1"), None)
    winner_time_s = None
    winner_laps = None
    if winner:
        millis = winner.get("Time", {}).get("millis")
        if millis:
            winner_time_s = int(millis) / 1000
        else:
            winner_time_s = parse_time(winner.get("Time", {}).get("time"))
        winner_laps = int(winner.get("laps", 0) or 0)

    # Build qualifying lookup keyed by driverId
    qual_by_driver: dict[str, dict[str, Any]] = {}
    pole_time_s = None
    if qual_doc:
        q_results = qual_doc["MRData"]["RaceTable"]["Races"][0].get("QualifyingResults", [])
        for q in q_results:
            qd = q.get("Driver", {})
            qtime = q.get("Q3") or q.get("Q2") or q.get("Q1")
            qts = parse_time(qtime)
            if qts and (pole_time_s is None or qts < pole_time_s):
                pole_time_s = qts
            qual_by_driver[qd.get("driverId")] = q

    # Compute pace per driver
    drivers_out: list[dict[str, Any]] = []
    for r in results:
        d = r.get("Driver", {})
        c = r.get("Constructor", {})
        status = r.get("status", "")
        laps_done = int(r.get("laps", 0) or 0)

        # Fastest lap
        fl = r.get("FastestLap", {})
        fl_time_s = parse_time(fl.get("Time", {}).get("time"))
        fl_rank = int(fl.get("rank")) if fl.get("rank") and fl.get("rank").isdigit() else None

        # Race pace average: only for drivers who finished
        # winner: pace = winner_time / laps
        # non-winner finisher: pace = (winner_time + gap_to_winner) / laps
        # DNF / +1 Lap / etc: pace = None
        pace_avg_s = None
        pace_delta_to_winner_s = None
        if status == "Finished" and winner_time_s and laps_done > 0:
            if r.get("position") == "1":
                pace_avg_s = winner_time_s / laps_done
                pace_delta_to_winner_s = 0.0
            else:
                gap_s = parse_time(r.get("Time", {}).get("time"))
                if gap_s is not None:
                    driver_total = winner_time_s + gap_s
                    pace_avg_s = driver_total / laps_done
                    pace_delta_to_winner_s = gap_s / laps_done

        # Qualifying
        q = qual_by_driver.get(d.get("driverId"))
        q_best = None
        q_pos = None
        q_gap_to_pole_s = None
        if q:
            q_time_str = q.get("Q3") or q.get("Q2") or q.get("Q1")
            q_best = q_time_str
            qts = parse_time(q_time_str)
            if qts and pole_time_s:
                q_gap_to_pole_s = round(qts - pole_time_s, 3)
            qp = q.get("position")
            if qp and qp.isdigit():
                q_pos = int(qp)

        drivers_out.append(
            {
                "driver_id": d.get("driverId"),
                "driver_name": f"{d.get('givenName', '')} {d.get('familyName', '')}".strip(),
                "permanent_number": d.get("permanentNumber"),
                "car_number": r.get("number"),
                "team_id": c.get("constructorId"),
                "team_name": c.get("name"),
                "pos": int(r["position"]) if r.get("position", "").isdigit() else None,
                "pos_text": r.get("positionText"),
                "grid": int(r["grid"]) if r.get("grid", "").isdigit() else None,
                "laps": laps_done,
                "status": status,
                "best_lap_s": fl_time_s,
                "best_lap_str": fmt_lap(fl_time_s),
                "best_lap_rank": fl_rank,
                "pace_avg_s": round(pace_avg_s, 3) if pace_avg_s else None,
                "pace_delta_to_winner_s": round(pace_delta_to_winner_s, 3) if pace_delta_to_winner_s is not None else None,
                "q_best_str": q_best,
                "q_best_s": parse_time(q_best),
                "q_pos": q_pos,
                "q_gap_to_pole_s": q_gap_to_pole_s,
            }
        )

    return {
        "round": rnd,
        "race": race.get("raceName", ""),
        "date": race.get("date", ""),
        "circuit": race.get("Circuit", {}).get("circuitName"),
        "laps_total": winner_laps,
        "winner_time_s": winner_time_s,
        "winner_time_str": winner.get("Time", {}).get("time") if winner else None,
        "pole_time_s": pole_time_s,
        "pole_time_str": fmt_lap(pole_time_s),
        "drivers": drivers_out,
    }


# ---------- per-team rollup ----------
def team_season_rollup(team_id: str, rounds: list[dict[str, Any]]) -> dict[str, Any]:
    team_rounds = []
    for rnd in rounds:
        team_drivers = [d for d in rnd["drivers"] if d["team_id"] == team_id]
        if not team_drivers:
            continue
        # Teammate comparison: which driver was faster this round?
        tm_delta = None
        tm_faster = None
        if len(team_drivers) >= 2:
            finishes = [d for d in team_drivers if d["pace_avg_s"] is not None]
            if len(finishes) >= 2:
                sorted_drivers = sorted(finishes, key=lambda d: d["pace_avg_s"])
                faster, slower = sorted_drivers[0], sorted_drivers[1]
                tm_delta = round(slower["pace_avg_s"] - faster["pace_avg_s"], 3)
                tm_faster = faster["driver_name"]
        # Qualifying comparison: best of the two drivers' Q times
        qualis = [d for d in team_drivers if d.get("q_pos") is not None]
        best_q_pos = min((d["q_pos"] for d in qualis), default=None)
        best_q_gap = min((d["q_gap_to_pole_s"] for d in qualis if d["q_gap_to_pole_s"] is not None), default=None)
        avg_q_pos = round(sum(d["q_pos"] for d in qualis) / len(qualis), 1) if qualis else None
        team_rounds.append({
            "round": rnd["round"],
            "race": rnd["race"],
            "date": rnd["date"],
            "drivers": team_drivers,
            "teammate_delta_s": tm_delta,
            "teammate_faster": tm_faster,
            "best_q_pos": best_q_pos,
            "best_q_gap_to_pole_s": round(best_q_gap, 3) if best_q_gap is not None else None,
            "avg_q_pos": avg_q_pos,
        })

    # Season aggregates
    races_started = len(team_rounds)
    wins = 0
    podiums = 0
    best_lap_s = None
    best_qual_s = None
    pace_deltas: list[float] = []
    positions: list[int] = []
    teammate_deltas: list[float] = []

    for rnd in team_rounds:
        for d in rnd["drivers"]:
            if d["pos"] is not None and d["status"] == "Finished":
                positions.append(d["pos"])
                if d["pos"] == 1:
                    wins += 1
                if d["pos"] <= 3:
                    podiums += 1
                if d["pace_delta_to_winner_s"] is not None:
                    pace_deltas.append(d["pace_delta_to_winner_s"])
            if d["best_lap_s"] and (best_lap_s is None or d["best_lap_s"] < best_lap_s):
                best_lap_s = d["best_lap_s"]
            if d["q_best_s"] and (best_qual_s is None or d["q_best_s"] < best_qual_s):
                best_qual_s = d["q_best_s"]
        if rnd["teammate_delta_s"] is not None:
            teammate_deltas.append(rnd["teammate_delta_s"])

    avg_pace_delta = round(sum(pace_deltas) / len(pace_deltas), 3) if pace_deltas else None
    positions_sorted = sorted(positions)
    median_pos = positions_sorted[len(positions_sorted) // 2] if positions_sorted else None
    avg_tm_delta = round(sum(teammate_deltas) / len(teammate_deltas), 3) if teammate_deltas else None
    max_tm_delta = max(teammate_deltas) if teammate_deltas else None

    return {
        "races_started": races_started,
        "wins": wins,
        "podiums": podiums,
        "best_lap_s": best_lap_s,
        "best_lap_str": fmt_lap(best_lap_s),
        "best_qual_s": best_qual_s,
        "best_qual_str": fmt_lap(best_qual_s),
        "avg_pace_delta_to_winner_s": avg_pace_delta,
        "median_position": median_pos,
        "avg_teammate_delta_s": avg_tm_delta,
        "max_teammate_delta_s": max_tm_delta,
        "by_round": team_rounds,
    }


# ---------- main ----------
def main() -> int:
    logger = setup_logging()
    logger.info("=== derive_pace.py start ===")

    rfs = race_files()
    if not rfs:
        logger.error("no race files found in %s", DATA_DIR)
        return 1
    logger.info("found %d race files", len(rfs))

    rounds: list[dict[str, Any]] = []
    for path in rfs:
        slug = path.stem  # r6-monaco
        qual_path = DATA_DIR / f"{slug}-qualifying.json"
        race_doc = load_json(path)
        if not race_doc:
            continue
        qual_doc = load_json(qual_path) if qual_path.exists() else None
        rounds.append(pace_for_round(race_doc, qual_doc))

    # Discover team_ids in stable order (from CONSTRUCTORS.json if present,
    # else by first appearance in round 1)
    team_ids: list[str] = []
    seen: set[str] = set()
    for rnd in rounds:
        for d in rnd["drivers"]:
            tid = d["team_id"]
            if tid and tid not in seen:
                team_ids.append(tid)
                seen.add(tid)

    teams_out = []
    for tid in team_ids:
        rollup = team_season_rollup(tid, rounds)
        teams_out.append({"team_id": tid, "season": rollup})

    out = {
        "generated_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "methodology": (
            "Per-team pace statistics derived from official race classification + "
            "qualifying JSONs. Pace = total_race_time / laps_completed, where total_race_time "
            "is reconstructed from winner_time + gap_to_winner. Only drivers who Finished "
            "contribute to pace aggregates. DNFs, +N Lap, and 107% classified drivers carry "
            "no pace figure. Best Q time is the best of Q3 (or Q2 / Q1 if no Q3). "
            "This is RACE AVERAGE pace; stint-level analysis (e.g. tyre-offset) requires "
            "per-lap telemetry, which is not available from Jolpica. See also: OpenF1 laps/stints "
            "endpoints currently return 404 for 2026 sessions; revisit when available."
        ),
        "rounds_covered": [
            {
                "round": r["round"],
                "name": r["race"],
                "date": r["date"],
                "circuit": r["circuit"],
                "laps": r["laps_total"],
                "winner_time_str": r["winner_time_str"],
                "pole_time_str": r["pole_time_str"],
            }
            for r in rounds
        ],
        "teams": teams_out,
    }

    out_path = DATA_DIR / "pace-dashboard.json"
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    logger.info(
        "wrote %s: %d teams, %d rounds",
        out_path.name,
        len(teams_out),
        len(rounds),
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
