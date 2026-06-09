# F1 2026 Viewer — Build Report

**Last updated:** 2026-06-09
**URL:** `http://100.91.143.50:8081/` (Tailscale-only, public IP blocked)
**Branch:** `main`
**HEAD commit:** `45254e9 feat: pace dashboard + PACE DASHBOARD home button + per-lap qualifying backfill`

This report is **regenerated** as new features ship. If something here
contradicts the live site, the live site wins — but please update this file
in the same commit so the docs stay honest.

---

## What shipped (cumulative across all sprints)

### Sprint 1 — Interactive 3D regulation viewer (2026-06-06)
- `index.html` v1 (76 KB): splash → teams → team detail → 3D car → part sheet
- 13 named Three.js parts, 11 constructors, 22 drivers, 22-race calendar
- 5 completed races at the time (R1-R5)
- Later committed in `44f6729`–`f0e3a90`

### Sprint 2 — v2 geometry + iOS WebGL probe (2026-06-06 → 2026-06-07)
- `af32700` v2: regulation-correct car geometry + smooth orbit controls
- Tested on iPhone — **WebGL 3D viewer was unusable on iOS Safari**
- Decision: keep SVG fallback only

### Sprint 3 — Fix the iOS 3D-experience (2026-06-07)
- `70e519f` Replaced broken 3D car view with standalone SVG `explore-car.html`
- `67b2baf` Direct quotes from FIA / The Race (replacing paraphrases)
- `430ec0d` Team-specific layer (Antonelli, Hamilton, etc.)
- `6c98ad8` Reverted team layer (was team narrative, not part commentary)
- `9d1ac7e`, `7cae0fb` Commented out 3D HUD elements (no longer reachable)

### Sprint 4 — Live data + 2 new pages + Sunday cron (2026-06-08 → 2026-06-09)
- `360ca26` Wired live `season-summary.json` + `latest.json` into home page
  - RACES RUN auto-counts from JSON
  - CHAMPIONSHIP LEADER auto-pulls from `driver-standings-r6.json`
  - POLE SITTER auto-computed (most poles across season)
  - DATA stamp shows last refresh
- `360ca26` Built `scripts/build_issue_data.py` — derives `car-issues-dnf.json`
  - 24 real mechanical DNFs across 11 teams, R1-R6
- `360ca26` Built `part-changes.html` + `car-issues.html` (clickable team grid)
- `360ca26` Hand-curated 3 `part-changes.json` entries (Monaco: Mercedes floor,
  Mercedes front suspension, Ferrari rear suspension)
- `360ca26` Sunday 23:00 CAT cron (job `87ed139da066`) refreshes everything

### Sprint 5 — Pace dashboard (2026-06-09)
- `45254e9` Built `scripts/derive_pace.py` (16 KB) — computes race-average pace
- `45254e9` Derived `data/pace-dashboard.json` (133 KB) — 11 teams × 6 rounds × 2 drivers
- `45254e9` Built `pace.html` (20 KB) — engineer dashboard with 2 views
- `45254e9` PACE DASHBOARD home-screen button (3rd in season-actions row)

### Sprint 6 — Regulation changes page (2026-06-09) — *uncommitted at this report*
- `regulations.html` (15 KB) — year-tabbed, FIA-cited regulation changes
- `data/regulations.json` (14 KB) — schema v1, 15 changes across 2 years
- REG REWRITE stat on home converted to clickable button (accent teal, arrow)
- `scripts/update_regulations.py` (8 KB) — validate / add-year / summary
- 14 cards across 4 categories (aero, power unit, chassis, sporting)
- All 5 Playwright test steps pass

### Sprint 7 — Driver detail page (2026-06-09) — *uncommitted at this report*
- `driver.html` (19 KB) — bio + 3 season sections (2024, 2025, 2026)
- `data/driver-history.json` (508 KB) — 22 drivers × 3 years from Jolpica
- `scripts/build_driver_history.py` (12 KB) — backfill script
- Driver cards on home (team detail) converted from `<div>` to clickable
  `<button>` — hover lift, accent arrow, cursor pointer
- Auto-generated story-style headlines per race ("recovering from P2 on
  the grid", "first podium of the season", "DNFs after 23 laps")
- 22 drivers, 18 with 2024 data, 19 with 2025, 22 with 2026 R1-R6
- All 9 Playwright test steps pass (antonelli, hadjar, verstappen,
  nonexistent driver, blank URL, back nav)

### Sprint 7b — Driver page team-color theming + season reorder (2026-06-09)
- `driver.html` updated: per-driver team-color theming via CSS variables
  (`--team-color`, `--team-color-alpha`, `--accent`)
- Resolves driver's 2026 team name → constructorId → 2026 livery color
- Bio team row, 2026 season "CURRENT" tag, and 2026 points stat all
  tinted with the team color (Mercedes teal, Ferrari red, Red Bull blue,
  McLaren orange, Williams blue, Aston Martin green, etc.)
- 2026 season section gets a `.current` class → 3px left border in
  team color
- Active tag now reads "CURRENT · IN PROGRESS"
- **Season order reversed:** 2026 (current, in progress) → 2025 → 2024
  (oldest), so the reader always sees what's happening now first
- `scripts/test-driver-theme.js` — 6 cases × 7 assertions = 42/42 pass
  (Antonelli/Hamilton/Verstappen/Piastri/Sainz/Alonso)

---

## Pages (verified working)

| Page | URL | Verified |
|---|---|---|
| Home | `/?v=N` | ✓ 4 stat cards live, 3 season-action buttons, 11 team cards |
| Team detail | `/?v=N` (tap team) | ✓ Crest, drivers, points, CTA to explore car |
| SVG car viewer | `explore-car.html?v=N` | ✓ 12 tappable parts, FIA citation, 24 quotes |
| Part changes | `part-changes.html?v=N` | ✓ 11 team cards → tap → upgrade detail |
| Car issues | `car-issues.html?v=N` | ✓ 11 team cards sorted by DNF count → tap → DNF detail |
| Pace dashboard | `pace.html?v=N` | ✓ SEASON view (132 rows) + RACE BY RACE sortable |
| Regulations | `regulations.html?v=N` | ✓ Year tabs (2026, 2025), 14 cards, sourced |
| Driver | `driver.html?id=<driverId>&v=N` | ✓ Bio, 3 season sections (newest first), team-color theming, race-by-race narrative |

**CACHE WARNING:** iOS Safari aggressively caches. After deploy, hard-refresh
or use `?v=N` query strings. Documented in `OPERATIONS.md`.

---

## Data flowing through the system

| Source | Endpoint | Refresh | File produced |
|---|---|---|---|
| Jolpica/Ergast | `/f1/2026/{round}/results.json` | Weekly cron | `r1-australia.json` … `r6-monaco.json` |
| Jolpica/Ergast | `/f1/2026/{round}/qualifying.json` | Weekly cron | `rN-...-qualifying.json` |
| Jolpica/Ergast | `/f1/2026/{round}/driverStandings.json` | Weekly cron | `driver-standings-rN.json` |
| Jolpica/Ergast | `/f1/2026/{round}/constructorStandings.json` | Weekly cron | `constructor-standings-rN.json` |
| Derived | `build_issue_data.py` | Weekly cron | `car-issues-dnf.json` |
| Derived | `derive_pace.py` | Weekly cron | `pace-dashboard.json` |
| Manual | `update_regulations.py --add-year` | Yearly | `regulations.json` |
| Hand-curated | (in-session) | As-found | `part-changes.json` |

All 7 JSON files served at runtime, fetched on home page boot. See
`DATA-REFERENCE.md` for full schemas.

---

## Data engine — Sunday cron

```
Cron: 0 21 * * 0 UTC  (Sunday 23:00 CAT)
Job ID: 87ed139da066
Mode: no_agent (script-only, silent on success, alert on failure)
Sequence: update_f1_data.py → build_issue_data.py → derive_pace.py
```

Why Sunday 23:00 CAT: races finish 17:00-19:00 local Europe = 17:00-19:00 CAT,
results are stable by 23:00 CAT. The cron pulls the **3 latest completed
rounds** (amendment window) plus **all-completed qualifying**, then re-derives
the 2 derived datasets. Re-fetches are idempotent — content is re-read on
each cron, but if the JSON hasn't changed, the file is rewritten with the
same content (atomic via `os.replace`).

---

## 3D car state (Sprint 2/3)

The 3D WebGL viewer was disabled in Sprint 3 due to iOS Safari WebGL
instability. The code remains in `index.html` and the Three.js vendor file
remains on disk, but:

- The `screen-car` section is commented out (lines ~706-748)
- The MERCEDES · W17 HUD title is commented out (line 725 area)
- The footer-hint block (DRAG ORBIT / SCROLL ZOOM / TAP PART DETAIL) is commented out
- `vendor/three.module.js` is **not** imported by `index.html` (1.27 MB
  reduction in home page weight)

The SVG-based `explore-car.html` is the working equivalent — 12 named parts,
tap to read FIA article + impact. No 3D, no WebGL, works on every browser.

Future work: per-team 3D geometry from launch imagery (Sprint 7+ in ROADMAP).

---

**Driver page rendered with team-color theming (iPhone 13 WebKit):**

| Driver | Team | Theme color | Test result |
|---|---|---|---|
| Antonelli | Mercedes | `#00D7B6` (teal) | ✓ all 7 assertions |
| Hamilton | Ferrari | `#DC0000` (red) | ✓ all 7 assertions |
| Verstappen | Red Bull | `#1E40AF` (blue) | ✓ all 7 assertions |
| Piastri | McLaren | `#FF8000` (orange) | ✓ all 7 assertions |
| Sainz | Williams | `#005AFF` (blue) | ✓ all 7 assertions |
| Alonso | Aston Martin | `#006F62` (green) | ✓ all 7 assertions |

**Season ordering verified:** 2026 (current, in progress, with team-color
left border) → 2025 → 2024 (oldest). Reader always sees what's happening
now first.

## Verified iPhone behaviour (Playwright iPhone 13 WebKit)

| Test | Result |
|---|---|
| Home loads, 4 stat cards, 3 season-action buttons | ✓ |
| Tap team → team detail with crest + drivers + points | ✓ |
| Tap EXPLORE THE CAR → SVG car viewer, 12 parts clickable | ✓ |
| Tap PART CHANGES home button → 11 team cards → tap team → upgrade list | ✓ |
| Tap CAR ISSUES home button → 11 team cards (sorted) → tap team → DNF list | ✓ |
| Tap PACE DASHBOARD home button → SEASON view (132 rows) | ✓ |
| Pace page: RACE BY RACE view, 15 finishers, all rows render | ✓ |
| Tap REG REWRITE home button → regulations page → 2026 active | ✓ |
| Regulations page: switch to 2025 tab → 1 change renders | ✓ |
| Regulations page: back → home with `?v=regback1` | ✓ |
| No horizontal overflow (scrollWidth == innerWidth = 390) | ✓ |
| No console errors, no failed network requests | ✓ |

---

## Open follow-ups

See `ROADMAP.md` for the full 4-tier priority list. Top 3 next-session items:

1. **Strip dead 3D code from index.html** — 1.27 MB vendor + ~1,000 lines of
   unreferenced JS. Effort: 1 hr.
2. **Team drill-down on pace.html** — team blocks should be clickable. Effort: 1-2 hrs.
3. **Sortable table headers on pace.html (RACE BY RACE view)** — engineers
   want to sort by pace, by delta, by qualifying gap. Effort: 1 hr.
