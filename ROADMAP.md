# Roadmap

> Last updated: 2026-06-09

The viewer is **production-quality for the current sprint scope** (5 pages +
Sunday cron + live data + sourced regulations). This document captures the
**next 6 months of work**, organized by priority tier. Effort estimates are
honest — these were sized when the items were discussed, not after the fact.

## Priority legend

- 🔴 **P0** — high engineer value, low cost, do next sprint
- 🟡 **P1** — high value, medium cost, plan within 1 month
- 🟢 **P2** — value-add, plan within 3 months
- 🔵 **P3** — nice-to-have, opportunistic

---

## P0 — Do next sprint (~5 hours total)

### 1. Strip dead 3D code from `index.html`
- **Value:** 5/5 (perf) — 1.27 MB Three.js vendor + ~1,000 lines of unreferenced JS
- **Cost:** 1 hr
- **What:** Remove `initThree()`, `renderCarView()`, the commented `#screen-car`
  block (lines ~706-748), and `vendor/three.module.js` via `git rm`.
- **Why now:** We're not coming back to the 3D viewer. Carrying the dead code
  is pure cost.
- **Risk:** Low. All referenced code (SVG viewer in `explore-car.html`) is
  independent of Three.js.

### 2. Team drill-down on `pace.html`
- **Value:** 5/5 (UX) — engineers want to drill into a single team's history
- **Cost:** 1-2 hrs
- **What:** Make each team block in the SEASON view clickable → opens a
  team-detail view showing only that team's race-by-race pace, qualifying,
  teammate delta, wins/podiums.
- **Data:** No new fetch needed — `pace-dashboard.json` already has the
  per-team-per-round breakdown.
- **Pattern:** Reuse the part-changes / car-issues click-to-drill pattern.

### 3. Sortable table headers on `pace.html` (RACE BY RACE view)
- **Value:** 5/5 (UX)
- **Cost:** 1 hr
- **What:** Make the 8-column table sortable (team, pace, delta, qualy, qualy
  gap, wins, podiums, median). Click header → sort asc, click again → desc.
- **Library:** None. Pure JS sort on the rendered DOM, or sort the data
  before render.

---

## P1 — Within 1 month (~20 hours total)

### 4. Team-vs-team comparison view
- **Value:** 5/5 (intel) — the killer competitive-intelligence feature
- **Cost:** 3 hrs
- **What:** New `compare.html`. Pick 2 teams via dropdowns. Show their
  per-round pace side-by-side, deltas, qualifying gaps, in a single view.
- **Data:** Already in `pace-dashboard.json`. Pure presentation.

### 5. "Next race" countdown on home screen
- **Value:** 3/5 (UX) — engineers/strategists plan around the next race
- **Cost:** 30 min
- **What:** Pill on home: "NEXT: BARCELONA GP · 6 DAYS" pointing at R7.
- **Data:** `season-summary.json` has race dates. Compute days-to-next-race
  in JS, no fetch.

### 6. Per-lap data ingestion (real Tier-1 telemetry)
- **Value:** 4/5 — opens the door to tyre-strategy intelligence
- **Cost:** 1-2 hrs (cron) + 4-6 hrs (viz)
- **What:**
  1. Add `/laps.json` + `/pitstops.json` fetch to `update_f1_data.py`
     (~1,400 + 86 records per race, ~200 KB/race, 1.4 MB/season)
  2. Add tyre-degradation curve visualisation to `pace.html`:
     pace vs tyre age per team per race
  3. Pit crew performance leaderboard on `car-issues.html` or new
     `pit-crew.html` (fastest stops, % within 2.5s, consistency)
  4. Driver consistency scatter (stddev of lap times per driver, color by
     team)
- **Why now:** This is what makes the portal genuinely useful to a real
  team engineer. Without it, we're a results journal.

### 7. Driver page
- **Value:** 4/5 — uses the 24 cached quotes from The Race
- **Cost:** 2-3 hrs
- **What:** `drivers.html` — driver grid, tap driver → bio + season stats
  (wins, podiums, points, best qualy) + 2-3 sourced quotes.
- **Data:** Drivers from `drivers.json`, stats from `pace-dashboard.json`
  (already per-driver), quotes cached in session memory (need to be
  persisted to `data/driver-quotes.json` first).

### 8. Constructors points trajectory chart
- **Value:** 4/5 — gap-to-P1 over rounds tells the season story
- **Cost:** 1-2 hrs
- **What:** SVG line chart, no library. X = round, Y = points. 11 lines,
  one per team. Highlight the leader, fade the rest.
- **Data:** Need to backfill standings per round (not just R6). Jolpica
  endpoint: `/f1/2026/{round}/constructorStandings.json` for R1-R6.

---

## P2 — Within 3 months

### 9. Part-changes growth: media keyword scrape
- **Value:** 4/5 — the 3-entry hand-curated seed is too thin
- **Cost:** 4-6 hrs
- **What:** Python scraper (The Race, RaceFans, motorsport.com) for
  "upgrade" / "new floor" / "brought" / "introduced" keywords per round
  per team. Auto-append to `part-changes.json` with source URL.
- **Risk:** Article scraping is fragile. Need rate-limiting, source
  attribution, and a human-review pass before committing.

### 10. PWA / offline mode
- **Value:** 3/5 — flight-attendant-friendly read-it-on-the-plane
- **Cost:** 2 hrs
- **What:** Service worker that caches all `data/*.json` + HTML on first
  visit. Serve from cache on no-network.
- **Library:** None. Hand-rolled service worker with explicit cache list.

### 11. Track-by-track heatmap
- **Value:** 3/5 — circuit × team grid showing each team's average finish
  position per track
- **Cost:** 2-3 hrs
- **What:** New `tracks.html`. Rows = 6 completed tracks, columns = 11 teams.
  Cell = avg finish position. Color-coded (green = podium, red = back of
  field).
- **Data:** All from `pace-dashboard.json` and race results.

### 12. Tests for the 3 derived-data scripts
- **Value:** 4/5 (operational) — catches regressions when Jolpica changes shape
- **Cost:** 2 hrs
- **What:** Pytest unit tests for `update_f1_data.py`, `build_issue_data.py`,
  `derive_pace.py`. One assertion per script: "Mercedes has 6 wins after R6",
  "Ferrari has 24% DNF rate", "Verstappen pace delta is <0.5s".
- **Why now:** If a future Ergast API change breaks the data pipeline, we
  want CI to fail loudly.

### 13. Bundle cross-page navigation
- **Value:** 2/5 (UX) — small but polished
- **Cost:** 1 hr
- **What:** Add a small top-nav (logo + 5 page links) to all 5 secondary
  pages. Currently you have to go back to home to switch.

---

## P3 — Opportunistic

### 14. OpenF1 telemetry integration (when it comes back)
- **Value:** 5/5 if available — real per-lap data, tyre compounds, pit windows
- **Cost:** Variable (8-12 hrs for visualisation layer)
- **Status:** BLOCKED — `laps`/`stints`/`pit` endpoints 404 for all 2026
  session keys. Documented in ARCHITECTURE Sprint 5 trade-off.
- **When:** Retry monthly. If 2026 sessions start returning data, build the
  tyre-deg and stint-pace visualisations.

### 15. Per-team 3D geometry (the original 3D dream)
- **Value:** 4/5 (visual) — but SVG works fine
- **Cost:** 40+ hrs (modeling all 11 cars from launch imagery)
- **Why deferred:** WebGL is unreliable on iOS Safari. We'd need a non-WebGL
  fallback anyway. The SVG viewer covers 90% of the value.
- **When:** If we get a designer with CAD access, or a partnership with a
  team that shares 3D models.

### 16. AWS Fan Vision / F1 TV Pro scrape
- **Value:** 5/5 if partnership — onboard video frame analysis
- **Cost:** 60+ hrs (partnership negotiation + frame analysis pipeline)
- **Status:** AWS partnership is post-2025, requires real commercial
  relationship. Aggressive F1 TV Pro scraping is legally grey.
- **When:** When there's a business case for the time investment.

### 17. Press-release scrape (option A from Sprint 4)
- **Value:** 3/5 — more work than the media scrape, marginal higher signal
- **Cost:** 6-8 hrs
- **Status:** Deferred in favour of option B (media keyword scrape, item 9).

### 18. Light mode toggle
- **Value:** 1/5 (cosmetic)
- **Cost:** 1 hr
- **When:** If a user actually asks for it. Dark is the brand.

### 19. Search across drivers / teams / races
- **Value:** 2/5 — useful only when driver pages land
- **Cost:** 1-2 hrs (cmd-K style)
- **When:** After item 7 (Driver page) ships.

### 20. Driver comparison within a team (Antonelli vs Russell chart)
- **Value:** 4/5 — same data, better story
- **Cost:** 1-2 hrs
- **When:** Could be a Sprint 7 alternative to item 7 (Driver page).

---

## Suggested next-session menu

If Sir wants a quick session, do P0 (5 hours, 3 items).
If Sir wants a heavier push, do P0 + P1 #4 (8 hours, 4 items).
If Sir wants the next "killer feature", do P1 #6 (tyre deg) — that's what
turns the portal from "results journal" to "strategy tool".

---

## What we'll never do

- Mock data of any kind (Sir's mandate)
- Public access (Tailscale-only is the security model)
- Heavy frameworks (React, Vue, Svelte) — the static-only model is the point
- Auto-commits from cron — git is for human review
