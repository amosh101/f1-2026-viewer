# Architecture

This document captures the **why** behind the F1 2026 Viewer — the design
decisions, the trade-offs, and the constraints that shaped the codebase.
Read this before making structural changes.

---

## High-level shape

```
        ┌─────────────────────────────────────┐
        │   Tailscale-only static server      │
        │   python3 -m http.server 8081       │
        │   bound to 100.91.143.50            │
        └────────────┬────────────────────────┘
                     │
   ┌─────────────────┼─────────────────────────────────┐
   │                 │                                  │
┌──▼────┐  ┌────────▼─────┐  ┌──────────┐  ┌────────┐  ┌▼──────────┐
│ Home  │  │ SVG car      │  │ Part chgs│  │ Issues │  │ Pace      │
│ index │  │ explore-car  │  │ part-    │  │ car-   │  │ pace.html │
│ .html │  │ .html        │  │ changes  │  │ issues │  │           │
│       │  │              │  │ .html    │  │ .html  │  │           │
└───────┘  └──────────────┘  └──────────┘  └────────┘  └───────────┘
   │              │                │             │             │
   │              │                │             │             │
   └──────────────┴────────┬───────┴─────────────┴─────────────┘
                           │
                  ┌────────▼─────────┐
                  │  data/*.json     │  ← served as static files
                  │  (~540 KB total) │
                  └────────▲─────────┘
                           │
              ┌────────────┴────────────┐
              │                         │
       ┌──────┴───────┐         ┌──────▼──────────┐
       │ Sunday cron  │         │ Manual / yearly │
       │              │         │                 │
       │ • update     │         │ • update_regu-  │
       │   _f1_data   │         │   lations.py    │
       │ • build_issue│         │   --add-year    │
       │   _data      │         │                 │
       │ • derive_pace│         │ • hand-curated  │
       │              │         │   part-changes  │
       └──────┬───────┘         └──────┬──────────┘
              │                        │
              ▼                        ▼
       ┌──────────────┐         ┌──────────────┐
       │ Jolpica/     │         │ FIA / The    │
       │ Ergast API   │         │ Race / etc.  │
       │ (free)       │         │ (manual)     │
       └──────────────┘         └──────────────┘
```

Key architectural choices:

- **Static, no build step.** Every page is a self-contained HTML file with
  embedded CSS and inline JS. No bundler, no transpiler, no `node_modules`.
  You can read the source by viewing the page.
- **No backend.** All data lives in `data/*.json`, refreshed by Python
  scripts. The "data engine" is the Sunday cron.
- **No framework.** No React, no Vue, no Svelte. Just ES module JS.
- **CDN dependencies only.** Three.js (legacy, not loaded by home) and Inter
  (Google Fonts) come from CDN. No npm runtime.

---

## The 5 pages

| Page | Why this page exists |
|---|---|
| **Home** (`index.html`) | The front door. Live season summary, team picker, season-action buttons. Auto-pulls RACES RUN, CHAMPIONSHIP LEADER, POLE SITTER, DATA stamp from JSON. |
| **SVG car viewer** (`explore-car.html`) | Replaces the broken 3D viewer. 12 tappable parts, FIA Tech Regs article citation per part, 24 direct quotes from The Race. Works on iPhone, no WebGL. |
| **Part changes** (`part-changes.html`) | Tracks team upgrades round-by-round. Hand-curated seed (3 entries from Monaco). Team cards → click team → upgrade list. |
| **Car issues** (`car-issues.html`) | Mechanical DNFs across the season. Auto-derived from race results (24 issues). Team cards sorted by DNF count. |
| **Pace dashboard** (`pace.html`) | Engineer view: race-average pace per team per round, teammate delta, qualifying gaps, wins/podiums. Two views: SEASON (per-team detail) + RACE BY RACE (sortable table). |
| **Regulations** (`regulations.html`) | Year-on-year FIA regulation changes. Year tabs (2025, 2026), categories (aero, power unit, chassis, sporting), each change sourced to FIA Tech Regs article. The +70% "biggest rewrite" is a clickable stat on home. |

---

## Data flow

### At boot (every page)

1. Browser hits `index.html`.
2. `refreshLiveData()` fires 7 `fetch()` calls in parallel:
   - `data/latest.json` — pointer to current round
   - `data/season-summary.json` — 6 rounds of podium/qualifying summary
   - `data/constructor-standings-r6.json`
   - `data/driver-standings-r6.json`
   - `data/part-changes.json`
   - `data/car-issues-dnf.json`
   - `data/pace-dashboard.json`
   - `data/regulations.json`
3. Globals (`SEASON_SUMMARY`, `CONSTRUCTOR_STANDINGS`, etc.) get overwritten.
4. `renderTeams()` reads the globals, paints 4 stat cards + 3 buttons + 11 teams.

Cache buster: every page uses `?v=N` query strings. After deploy, hard-refresh
on iPhone.

### At Sunday 23:00 CAT (cron)

1. `update_f1_data.py` runs:
   - Fetches 3 latest completed rounds of results + standings
   - Fetches **all completed rounds** of qualifying (cheap, ~525 records each)
   - Updates `latest.json` pointer
   - Rebuilds `season-summary.json` from race + qualifying data
2. `build_issue_data.py` runs:
   - Walks R1-R6 race files, extracts DNFs with mechanical/electrical status
   - Excludes collision/accident/spun-off/lapped
   - Writes `car-issues-dnf.json`
3. `derive_pace.py` runs:
   - Walks R1-R6 race files, computes `(winner_time + gap_to_winner) / laps_done` per team per round per driver
   - Computes teammate delta when both finish
   - Computes qualifying position+gap
   - Writes `pace-dashboard.json`

**No auto-commit.** The cron updates the JSONs; git is a separate step done
by Sir or assistant manually. This keeps the policy clear: data refreshes
are automatic, code changes are deliberate.

---

## Design decisions (the "why" log)

### 1. SVG instead of WebGL (Sprint 3)

**Decision:** Disable the 3D Three.js viewer, build an SVG car viewer in
`explore-car.html`.

**Why:** Tested on iPhone — WebGL canvas was unstable on iOS Safari, with
parts not rendering, the orbit camera locking, and shadow maps failing.
The SVG viewer has 12 tappable parts, no WebGL, no GPU dependency, and
works on every browser.

**Trade-off:** Lost the 3D rotation visual. The "EXPLORE THE CAR" button
still goes somewhere (the SVG viewer), and the FIA article citations and
impact notes are surfaced cleanly.

**Code in `index.html`:** The dead 3D code (initThree, renderCarView, the
`#screen-car` section) is still there. ~1,000 lines of unreferenced JS +
1.27 MB `vendor/three.module.js`. See ROADMAP sprint 1 for removal plan.

### 2. Sunday 23:00 CAT cron (Sprint 4)

**Decision:** Auto-refresh data every Sunday at 21:00 UTC (= 23:00 CAT).

**Why:** Race finishes are typically 17:00-19:00 local Europe. CAT is
UTC+2, so a race finishing at 19:00 local = 17:00 UTC. By 21:00 UTC (23:00
CAT) the Jolpica results are stable. Sir wanted the refresh to land when
he'd be planning for the next week.

**Trade-off:** Could miss late-amendment results. Mitigation: amendment
window of 3 latest rounds, so even if R6's results update on Tuesday, the
next Sunday's cron will catch R4-R6.

**Why not auto-commit:** Sir's policy — git is for human + assistant review,
not for cron. Auto-commits can ship broken JSON.

### 3. Race-average pace, not stint pace (Sprint 5)

**Decision:** `pace-dashboard.json` uses `(winner_time + gap_to_winner) / laps_done`
per team per round, not per-stint / per-lap.

**Why:** OpenF1's per-lap telemetry 404s for all 2026 session keys. We can
only get race-level data from Jolpica. Documented as a methodology limitation
on `pace.html`.

**Trade-off:** Misses tyre-strategy intelligence. We can't see "Mercedes's
pace was 0.5s/lap faster on hards than Ferrari on mediums". When OpenF1
comes back, the dashboard can be re-derived per stint.

### 4. Hand-curated `part-changes.json` (Sprint 4)

**Decision:** 3 entries (Monaco: Mercedes floor, Mercedes front suspension,
Ferrari rear suspension) hand-curated from The Race articles. Cited in JSON.

**Why:** No public API for "what upgrades did each team bring to each race".
Press-release scraping is in scope for Sprint 8 but not built. Hand-curation
honestly labels the dataset as thin.

**Trade-off:** 3 entries isn't enough for a serious season tracker. Mitigated
by the page making it obvious: "Tracked team upgrades · R1 → latest" sub-text,
and the team card showing 0 changes honestly.

### 5. No mock data policy

**Decision:** Every value displayed must be either (a) live-fetched from
a public API at runtime, (b) hand-curated and source-attributed, or
(c) auto-derived from (a) or (b).

**Why:** Sir's mandate after the `flight_scraper.py` incident
(2026-04-08). Mock data erodes trust in everything produced.

**Implementation:** All JSONs in `data/` are real. `regulations.json` is
explicitly sourced (FIA Tech Regs article numbers). `part-changes.json` is
explicitly hand-curated. The pace methodology is documented on the page.
The regulation change_pct field is `null` when the change is qualitative
(not a numeric delta) — this is more honest than guessing a number.

### 6. Single static server, no API layer

**Decision:** Use `python3 -m http.server` bound to Tailscale IP. No
reverse proxy, no TLS termination on the box, no separate API server.

**Why:** The app is read-only and small. Tailscale gives us private network
access. The "data engine" runs on the box, writes JSON to disk, and the
HTTP server serves them. No reason to add a backend.

**Trade-off:** Tailscale-only. Anyone not on the Tailscale network can't
access. By design.

**Future:** When telemetry integration happens (if it does), there'll be
a real reason to add a backend (live data streams, FastestF1 caching).
Until then, the constraint is honest.

### 7. Playwright tests in iOS WebKit (all sprints)

**Decision:** Test against Playwright iPhone 13 WebKit, not Chrome.

**Why:** Sir's actual device is iPhone. If it doesn't work on WebKit, it
doesn't work for him. Chrome is irrelevant.

**Trade-off:** Playwright tests are 5-10x slower than Chrome unit tests.
Worth it for the iPhone-confidence guarantee.

### 8. Cache-buster `?v=N` query strings

**Decision:** All page links use `?v=N` where N increments per deploy.

**Why:** iOS Safari aggressively caches. Without the buster, a deploy
doesn't reach the device until the user manually clears cache or hard-
refreshes. With the buster, every link click is a forced fresh fetch.

**Trade-off:** Slightly more verbose URLs. Worth it for the deploy-reach
guarantee.

### 9. Pointer events on screens

**Decision:** `.screen { pointer-events: none; }` and only
`.screen.active { pointer-events: auto; }` for the active screen.

**Why:** Discovered during Sprint 4 — team-detail-screen button bindings
weren't firing on home screen until the home screen's `pointer-events`
were isolated. Without this, every screen's invisible buttons were
capturing clicks.

**Trade-off:** None. It's the right pattern for SPA-style screen routing.

### 10. Live data globals + `renderTeams()` re-run

**Decision:** `refreshLiveData()` overwrites globals (`SEASON_SUMMARY`,
`CONSTRUCTOR_STANDINGS`, etc.) with fetched data, then re-runs
`renderTeams()` if on the home screen.

**Why:** Race results change every week. The page must reflect them
without a deploy. Globals are overwritten; UI re-reads them.

**Trade-off:** The 1.4s splash is a deliberate "wait for data" pattern
during the boot fetch. Without it, the page would flash old data then
re-render.

---

## What we deliberately don't have (yet)

- **No WebGL 3D viewer** (iPhone issues, Sprint 3)
- **No telemetry integration** (OpenF1 404s, see Sprint 5 trade-off)
- **No team-vs-team comparison view** (planned Sprint 2 in ROADMAP)
- **No per-team unique geometry** (planned Sprint 7+ in ROADMAP)
- **No service worker / PWA** (planned Sprint 6 in ROADMAP)
- **No automated part-changes scraping** (planned Sprint 8 in ROADMAP)
- **No light mode** (deferred — dark theme is the brand)

---

## Constraints

- **iOS Safari is the primary target.** Every feature must work there.
- **Tailscale-only access.** No public URL.
- **Real data only.** No mocks, no fakes, no "for demonstration" labels.
- **Sunday cron is the only automatic refresh.** Code changes are deliberate.
- **No node_modules in the project.** Tests live in `/root/.npm/_npx/...`.
