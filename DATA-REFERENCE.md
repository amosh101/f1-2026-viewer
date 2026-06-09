# Data Reference

> Every JSON file in `data/`, with its schema, source, refresh cadence,
> and the page(s) that consume it.

If you add a new data file, add a section here in the same commit.

---

## `data/latest.json`

Pointer to the latest completed round. Home page reads this on boot.

```json
{
  "round": 6,
  "updated": "2026-06-08T17:48:00Z"
}
```

| Field | Type | Notes |
|---|---|---|
| `round` | int | 1-22, the latest round with stable results |
| `updated` | string ISO8601 UTC | When `update_f1_data.py` last wrote this file |

**Source:** Written by `update_f1_data.py` after each successful refresh.
**Refresh:** Weekly Sunday cron + manual via `python3 scripts/update_f1_data.py`.
**Consumers:** `index.html` (home stats).

---

## `data/season-summary.json`

Per-round summary: race name, date, top-3 finishers, pole sitter, fastest lap.

```json
{
  "1": {
    "round": 1,
    "name": "Australian Grand Prix",
    "slug": "australia",
    "date": "2026-03-15",
    "circuit": "Albert Park",
    "country": "Australia",
    "podium": [{"pos": 1, "driverId": "antonelli", "name": "Antonelli"},
               {"pos": 2, "driverId": "russell",   "name": "Russell"},
               {"pos": 3, "driverId": "hamilton",  "name": "Hamilton"}],
    "pole": "antonelli",
    "fastest_lap": {"driverId": "antonelli", "time": "1:19.231"}
  }
}
```

| Field | Type | Notes |
|---|---|---|
| keys | "1".."22" | Round number as string |
| `round` | int | Same as key |
| `name` | string | Official race name |
| `slug` | string | Country noun (NOT demonym) — used for filename slug |
| `date` | string YYYY-MM-DD | Race date in local time |
| `circuit` | string | Track name |
| `country` | string | Host country |
| `podium` | array of {pos, driverId, name} | Top 3 |
| `pole` | string | driverId of pole sitter |
| `fastest_lap` | {driverId, time} | Fastest lap in race |

**Source:** Jolpica `/f1/2026/{round}/results.json` + `/qualifying.json`.
**Refresh:** Weekly cron.
**Consumers:** Home page, future `tracks.html` (heat map), `pace.html` (RACE BY RACE view).

**Slug gotcha:** The slug function produces demonyms (`australian`); we
hard-override to nouns (`australia`) to match existing filenames. See
`update_f1_data.py` slug override table.

---

## `data/regulations.json`

Year-on-year FIA regulation changes. Schema v1, designed to be
additively extendable (add new year keys, never overwrite).

```json
{
  "schema_version": 1,
  "era_start": 2026,
  "headline": {
    "label": "BIGGEST RULES REWRITE",
    "value_pct": 70,
    "subtitle": "of the technical regulations changed vs 2022-2025",
    "source": "FIA / Formula 1 — 'the most comprehensive rules overhaul in four decades'",
    "source_url": "https://www.fia.com/news/..."
  },
  "years": {
    "2026": {
      "active": true,
      "regulation_pct": 70,
      "summary": "...",
      "source_label": "FIA — 2026 Technical Regulations",
      "source_url": "https://www.fia.com/regulation/category/110",
      "categories": {
        "aero": {
          "label": "AERODYNAMICS",
          "changes": [
            {
              "id": "aero-active-x-z",
              "title": "Active aerodynamics: X-Mode and Z-Mode",
              "summary": "DRS is replaced by two driver-selectable aero modes...",
              "change_pct": null,
              "change_pct_label": "REPLACES DRS",
              "source_label": "FIA Tech Regs Art. 3.10",
              "source_url": "https://www.fia.com/regulation/category/110",
              "impact": [
                "Removes the 'follow-the-leader' DRS problem",
                "Straight-line speed gains come from low-drag configuration",
                "Drivers manage mode selection on a corner-by-corner basis"
              ]
            }
          ]
        }
      }
    }
  }
}
```

| Top-level field | Type | Notes |
|---|---|---|
| `schema_version` | int | 1. Bump if you change the shape of a change object. |
| `era_start` | int | Year the current major regulation era began |
| `headline` | object | The single biggest-number stat (used on home) |
| `years` | object | Per-year content, keyed by year string |
| `future_years_note` | string (optional) | Editor instructions for future updates |

| Year field | Type | Notes |
|---|---|---|
| `active` | bool | Whether this is the current/featured year |
| `regulation_pct` | int | 0-100, headline rewrite % for this year |
| `summary` | string | 1-2 sentence overview of this year's regs |
| `source_label` | string | Human-readable citation |
| `source_url` | string | URL to the FIA portal or article |
| `categories` | object | Category key → {label, changes[]} |

| Change field | Type | Notes |
|---|---|---|
| `id` | string | Stable, kebab-case, unique within a year |
| `title` | string | Short, scannable |
| `summary` | string | 1-2 sentences explaining the rule change |
| `change_pct` | int or null | Numeric % change (e.g. MGU-H removed = -100). null for qualitative changes. |
| `change_pct_label` | string | Display label: "+300%", "REPLACES DRS", "rule enforced" |
| `source_label` | string | FIA Tech Regs Art. X.Y or external article title |
| `source_url` | string | URL to the citation |
| `impact` | array of strings | 2-4 bullet points, what this change means in practice |

**Source:** Hand-curated from FIA Technical Regulations portal + The Race
articles. No public FIA regulations API exists.
**Refresh:** Yearly via `python3 scripts/update_regulations.py --add-year YYYY`
then hand-edit the new year entries. Use `--summary` to print a table of
all years and `--validate` before committing.
**Consumers:** `index.html` (REG REWRITE stat), `regulations.html`.

**Validation:** `python3 scripts/update_regulations.py --validate` checks
schema, source_url/source_label/impact presence, returns non-zero on
failure. Add to CI before publishing.

---

## `data/pace-dashboard.json`

Per-team-per-round-per-driver race pace + teammate delta + qualifying gap.
133 KB. Built by `derive_pace.py`.

```json
{
  "schema_version": 1,
  "rounds_covered": [1, 2, 3, 4, 5, 6],
  "teams": [
    {
      "id": "mercedes",
      "name": "Mercedes",
      "season": {
        "avg_pace_delta_to_winner_s": 0.16,
        "wins": 6,
        "podiums": 8,
        "median_finish": 1.0,
        "best_qualy": "1:12.051",
        "best_qualy_round": 4
      },
      "rounds": [
        {
          "round": 1,
          "slug": "australia",
          "drivers": [
            {
              "driverId": "antonelli",
              "name": "Antonelli",
              "finish_pos": 1,
              "laps": 58,
              "pace_s_per_lap": 81.42,
              "gap_to_winner_s": 0.0,
              "qualifying": {"pos": 1, "time": "1:18.432", "gap_to_pole_s": 0.0},
              "teammate_delta_s": 4.5
            }
          ]
        }
      ]
    }
  ]
}
```

| Top field | Type | Notes |
|---|---|---|
| `schema_version` | int | 1 |
| `rounds_covered` | array of int | Which rounds have data |
| `teams` | array of team objects | One per constructor, sorted by season pace delta |

| Team field | Type | Notes |
|---|---|---|
| `id` | string | Constructor id (e.g. "mercedes", "ferrari") |
| `name` | string | Display name |
| `season` | object | Aggregated season stats |
| `rounds` | array of round objects | One per round the team has data for |

| Season stat | Type | Notes |
|---|---|---|
| `avg_pace_delta_to_winner_s` | float or null | Avg seconds/lap slower than race winner (0 = always wins) |
| `wins` | int | P1 finishes |
| `podiums` | int | Top-3 finishes (any driver) |
| `median_finish` | float | Median finishing position across both drivers |
| `best_qualy` | string | Best qualifying time across the season ("1:12.051") |
| `best_qualy_round` | int | Round of best qualifying |

| Round driver stat | Type | Notes |
|---|---|---|
| `driverId` | string | Driver id |
| `name` | string | Family name |
| `finish_pos` | int or null | Finishing position (null = DNF) |
| `laps` | int | Laps completed |
| `pace_s_per_lap` | float or null | Computed pace = (winner_time + gap_to_winner) / laps_done |
| `gap_to_winner_s` | float | Time gap to race winner at finish |
| `qualifying` | object or null | {pos, time, gap_to_pole_s} or null if not in qualifying |
| `teammate_delta_s` | float or null | Difference vs teammate's pace (positive = slower) |

**Source:** Derived from `data/r1-australia.json` etc. by `derive_pace.py`.
Race pace = `(winner_time_ms + gap_to_winner_ms) / laps_done`. Where
`gap_to_winner_ms` is the time gap for non-winners, and 0 for the winner.
**Refresh:** Weekly cron (after race files update).
**Consumers:** `pace.html`, home PACE DASHBOARD button.

**Methodology limitation:** This is **race-average pace**, not stint pace.
We can't see tyre-strategy intelligence (Mercedes 0.5s/lap faster on hards
than Ferrari on mediums) until OpenF1 telemetry comes back. Documented on
`pace.html`.

---

## `data/part-changes.json`

Team upgrades round-by-round. Hand-curated seed. 4 KB.

```json
{
  "schema_version": 1,
  "last_updated": "2026-06-08",
  "teams": {
    "mercedes": {
      "name": "Mercedes",
      "changes": [
        {
          "id": "mer-monaco-floor",
          "round": 6,
          "slug": "monaco",
          "part": "Floor",
          "title": "Revised floor edge wing",
          "summary": "Mercedes brought a revised floor edge wing...",
          "source_label": "The Race — Monaco GP tech analysis",
          "source_url": "https://www.the-race.com/..."
        }
      ]
    }
  }
}
```

| Field | Type | Notes |
|---|---|---|
| `schema_version` | int | 1 |
| `last_updated` | string YYYY-MM-DD | When the file was last hand-edited |
| `teams` | object | team id → {name, changes[]} |

| Change field | Type | Notes |
|---|---|---|
| `id` | string | Stable kebab-case, prefixed with team (e.g. "mer-monaco-floor") |
| `round` | int | 1-22 |
| `slug` | string | Country noun matching `season-summary.json` |
| `part` | string | Which car part was changed |
| `title` | string | Short title |
| `summary` | string | 1-2 sentence description |
| `source_label` | string | Where this was reported |
| `source_url` | string | URL to the source article |

**Source:** Hand-curated from The Race, RaceFans, motorsport.com articles.
**Refresh:** As articles are found. ROADMAP P1 #9 plans automated media
keyword scraping.
**Consumers:** `part-changes.html`.

**Honest coverage:** The page displays "3" for the season count, and team
cards show `0` for teams without documented upgrades. This is more honest
than a 0-vs-non-zero "coverage" badge.

---

## `data/car-issues-dnf.json`

Mechanical DNFs across the season. Auto-derived. 10 KB.

```json
{
  "schema_version": 1,
  "rounds_covered": [1, 2, 3, 4, 5, 6],
  "last_updated": "2026-06-08",
  "teams": [
    {
      "id": "aston_martin",
      "name": "Aston Martin",
      "issue_count": 6,
      "issues": [
        {
          "round": 2,
          "slug": "china",
          "driverId": "alonso",
          "name": "Alonso",
          "status": "Retired",
          "lap": 23,
          "summary": "Mechanical failure on lap 23"
        }
      ]
    }
  ]
}
```

| Field | Type | Notes |
|---|---|---|
| `schema_version` | int | 1 |
| `rounds_covered` | array of int | Rounds with DNF data |
| `last_updated` | string | When derived |
| `teams` | array of team objects | Sorted by issue_count desc |

| Issue field | Type | Notes |
|---|---|---|
| `round` | int | 1-22 |
| `slug` | string | Country noun |
| `driverId` | string | Driver id |
| `name` | string | Family name |
| `status` | string | "Retired" (the only status that means mechanical in Jolpica) |
| `lap` | int or null | Lap on which the DNF happened |
| `summary` | string | Human-readable |

**Source:** Derived by `build_issue_data.py` from race JSONs. Excludes
collision, accident, spun off, lapped (driver errors / race outcomes, not
car issues).
**Refresh:** Weekly cron.
**Consumers:** `car-issues.html`, home CAR ISSUES button.

**Limitation:** Jolpica doesn't tell us the specific mechanical subsystem
(engine vs gearbox vs hydraulics) — only generic "Retired" status. To get
that, we'd need a deeper source (FIA stewards documents, FIA press
releases, or team press releases).

---

## `data/constructor-standings-rN.json`

Constructor championship standings after round N. 4-5 KB.

```json
{
  "MRData": {
    "StandingsTable": {
      "season": "2026",
      "round": "6",
      "StandingsLists": [{
        "ConstructorStandings": [
          {
            "position": "1",
            "positionText": "1",
            "points": "244",
            "wins": "6",
            "Constructor": {
              "constructorId": "mercedes",
              "name": "Mercedes",
              "nationality": "German"
            }
          }
        ]
      }]
    }
  }
}
```

This is the raw Jolpica/Ergast shape — wrapped in `MRData.StandingsTable`.
**Source:** `https://api.jolpi.ca/ergast/f1/2026/6/constructorStandings.json`
**Refresh:** Weekly cron.
**Consumers:** `index.html` (CHAMPIONSHIP LEADER stat).

---

## `data/driver-standings-rN.json`

Driver championship standings after round N. 18 KB.

Same wrapper shape as constructor standings, but with `Driver` objects
instead of `Constructor`.
**Source:** Jolpica `/f1/2026/{round}/driverStandings.json`.
**Refresh:** Weekly cron.
**Consumers:** `index.html` (CHAMPIONSHIP LEADER stat, team detail).

---

## `data/rN-{slug}.json`

Race results for round N. 25-27 KB each.

Top-level: `MRData.RaceTable.Races[0].Results[]` — array of finishing
positions with driver, constructor, grid, laps, status, time, fastest lap.
**Source:** Jolpica `/f1/2026/{round}/results.json`.
**Refresh:** Weekly cron, latest 3 rounds re-fetched (amendment window).
**Consumers:** `pace.html` (RACE BY RACE view), `car-issues.html` (DNF
filtering), `pace-dashboard.json` derivation.

---

## `data/rN-{slug}-qualifying.json`

Qualifying results for round N. 18 KB each.

Top-level: `MRData.RaceTable.Races[0].QualifyingResults[]` — array with
driver, constructor, position, Q1/Q2/Q3 times.
**Source:** Jolpica `/f1/2026/{round}/qualifying.json`.
**Refresh:** Weekly cron, all completed rounds re-fetched.
**Consumers:** `pace-dashboard.json` (qualifying times), `pace.html`
qualifying column.

---

## `data/driver-history.json`

Per-driver per-season race history. 508 KB. Built by `build_driver_history.py`.

```json
{
  "schema_version": 1,
  "generated_utc": "2026-06-09T09:47:38Z",
  "source": "Jolpica/Ergast API + local 2026 race files",
  "drivers": {
    "max_verstappen": {
      "name": "Max Verstappen",
      "nationality": "Dutch",
      "permanent_number": "3",
      "history_2024": {
        "races_total": 24,
        "podiums": 14,
        "wins": 9,
        "best_finish": "P1",
        "points": 399,
        "races": [
          {
            "round": 1,
            "name": "Bahrain Grand Prix",
            "date": "2024-03-02",
            "qualifying": {"position": "1", "time": "1:29.179"},
            "finish": {"position": "1", "positionText": "1", "time": "1:31:44.742", "status": "Finished", "points": 25},
            "team": "Red Bull",
            "laps": 57,
            "grid": "1"
          }
        ]
      },
      "history_2025": {...},
      "season_2026_so_far": {...}
    }
  }
}
```

| Top field | Type | Notes |
|---|---|---|
| `schema_version` | int | 1 |
| `generated_utc` | string ISO8601 UTC | When `build_driver_history.py` last wrote this file |
| `source` | string | Where the data came from |
| `drivers` | object | driver id → driver entry |

| Driver entry field | Type | Notes |
|---|---|---|
| `name` | string | "Andrea Kimi Antonelli" |
| `nationality` | string | "Italian" |
| `permanent_number` | string | The car's permanent number |
| `history_2024` | object or null | 2024 season; null if driver was not in F1 in 2024 |
| `history_2025` | object or null | 2025 season; null if driver was not in F1 in 2025 |
| `season_2026_so_far` | object | Current 2026 season, R1-R6 |

| Season stat | Type | Notes |
|---|---|---|
| `races_total` | int | How many races in this season |
| `podiums` | int | P1/P2/P3 finishes |
| `wins` | int | P1 finishes |
| `best_finish` | string | "P1" or "DNF" |
| `points` | int | Championship points |
| `races` | array of race records | One per round |

| Race field | Type | Notes |
|---|---|---|
| `round` | int | 1-24 |
| `name` | string | "Australian Grand Prix" |
| `date` | string YYYY-MM-DD | Race date |
| `qualifying` | object or null | {position, time}; null if qualifying data unavailable |
| `finish.position` | string | "1"-"24" or "R" (Retired), "D" (DSQ) |
| `finish.positionText` | string | Same as position |
| `finish.time` | string | "1:31:44.742" (winner) or "+6.271" (gap) or empty |
| `finish.status` | string | "Finished", "Retired", "Accident", etc. |
| `finish.points` | int | Championship points awarded (0 for non-points positions) |
| `team` | string | Team name (driver can switch teams year-to-year) |
| `laps` | int | Laps completed |
| `grid` | string | Starting grid position |

**Source:** `build_driver_history.py` fetches 2024 + 2025 from Jolpica
(`/f1/{year}/drivers/{id}/results.json` + `qualifying.json`) and reads
2026 from local race files.
**Refresh:** Manual. Run `python3 scripts/build_driver_history.py` when
adding new drivers to the 2027 roster, or to re-fetch historical data.
**Consumers:** `driver.html` (the bio + season narrative pages).

**Driver id stability:** All 22 2026 driver IDs are stable across 2024
→ 2025 → 2026 (verified: antonelli, hamilton, russell, leclerc, piastri,
norris, max_verstappen, hadjar, lawson, gasly, bearman, colapinto,
arvid_lindblad, sainz, albon, ocon, bortoleto, alonso, hulkenberg,
bottas, perez, stroll). Rookies (hadjar, arvid_lindblad, bortoleto)
have null `history_2024` since they were not in F1 in 2024.

**Coverage:** 18 of 22 drivers have 2024 data (the 4 missing are the
2025/2026 rookies), 19 of 22 have 2025 data (bottas + perez had F1
sabbaticals; some rookies weren't in 2025 either), 22 of 22 have 2026 data.

---

## `data/constructors.json`, `drivers.json`, `driver-team-map.json`, `helmets.json`

Static reference data, captured 2026-06-06 from Jolpica + OpenF1. Not
refreshing because the 11 teams + 22 drivers don't change week-to-week.

| File | Size | Source | Consumer |
|---|---|---|---|
| `constructors.json` | 1.6 KB | Jolpica | Team cards (color, nationality) |
| `drivers.json` | 4.8 KB | Jolpica | Driver cards (number, name, DOB) |
| `driver-team-map.json` | 0.5 KB | Built from R5 results | Driver → team linkage |
| `helmets.json` | 0.5 KB | Manually captured | Driver helmet color in SVG viewer |

**Refresh:** Annually (when a new season starts and the team/driver roster
changes).

---

## `data/openf1-drivers-latest.json`

9 KB. Last OpenF1 drivers snapshot before the 2026 telemetry endpoints
went 404. Kept for reference; not actively consumed by any page.
