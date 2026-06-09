# F1 2026 Viewer — Browser MVP

> **This is the original design + scope spec from 2026-06-06**, before any
> code was written. The shipped product has evolved since — see:
>
> - `README.md` for the current page list and entry points
> - `BUILD-REPORT.md` for the verified current state
> - `ARCHITECTURE.md` for the design decisions that emerged
> - `ROADMAP.md` for what's planned next
> - `DATA-REFERENCE.md` for current data file schemas
> - `OPERATIONS.md` for server, cron, tests, iPhone workflow
>
> Kept for historical reference. The numbers and shape described below no
> longer reflect the shipped codebase (e.g. we no longer have a single
> 76 KB `index.html` — we have 6 pages, 4 cron scripts, and a 540 KB
> data directory).

## Mission
An interactive browser experience that teaches the 2026 F1 regulation era
through a sleek, dark, full-bleed UI. Pick a team, see the car, tap parts,
read specs, see how they did this season. Single HTML deliverable for
fastest iteration. iOS port follows after validation.

## Data sources (all real, no mocks)
- **Jolpica (Ergast mirror)** — 2026 season, drivers, constructors, race
  results, qualifying, driver/constructor standings.
- **OpenF1** — telemetry, driver numbers/teams, session info.
- **FIA 2026 Technical Regulations (publicly available summary)** — 12
  named parts with regulation citations.

## Verified data (cached in `./data/`)
- 11 constructors (Mercedes, Ferrari, Red Bull, McLaren, Aston Martin,
  Alpine, Williams, RB, Audi, Haas, Cadillac)
- 22 drivers, 22 races (Australia → Abu Dhabi, R6 Monaco = 2026-06-07
  is tomorrow, not yet raced)
- Round 5 (Canada, 2026-05-24): Antonelli (Mercedes) won, Hamilton P2
  for Ferrari
- 22 drivers in OpenF1 latest session

## Scope for v1 (THIS BUILD)
1. **Splash screen** with team-color sweep + 1.2s auto-dismiss
2. **Team grid** (11 teams) — click card → team detail
3. **Team detail** — 2 driver cards + car visual + "go to 3D" CTA
4. **3D car view** (Three.js) — 1 regulation-correct 2026 chassis
   per team, team livery, 12 tappable parts
5. **Part detail** sheet — spec + FIA regulation citation + impact note
   (telemetry-derived where possible)
6. **2026 season strip** — horizontal scroll through 22 races with
   results per car/driver
7. **Smooth transitions** between all screens (Framer-Motion-style
   CSS, no JS animation lib needed)

## Scope deferred to v2
- Per-driver detailed setup sheets (not in public data — confirmed)
- iOS port (SwiftUI + RealityKit) — after MVP validates
- All 11 teams in 3D (start with Mercedes W17 to validate
  pipeline, then expand — wire the data so it scales)
- Audio (engine sound) — licensing risk, deferred

## UI / Design system
- **Style:** SpaceX-inspired cinematic dark (pure black `#000` +
  spectral white `#f0f0fa`), uppercase + 0.96-1.17px letter-spacing,
  ghost buttons, full-bleed gradient surfaces.
- **Type:** Inter (CDN) — 700/400 only, D-DIN substitute.
- **Accent per team** — uses real team colors (Mercedes silver-petrol,
  Ferrari rosso, Red Bull navy/red/yellow, etc.) for the team
  card accent stripe + 3D car primary color.
- **Motion:** subtle, never decorative. 200-300ms easings,
  `prefers-reduced-motion` respected.

## Stack
- **Pure HTML/CSS/JS** — single `index.html` (no build step, no
  node_modules). Three.js loaded from esm.sh CDN pinned version.
- **Static server:** `python3 -m http.server 8081` (Tailscale-only)
- **No backend** — all data is pre-fetched into `./data/*.json` and
  served as static files.

## Routes
- `/` — splash → main menu (team grid)
- `#team/<id>` — team detail
- `#car/<teamId>` — 3D car with tappable parts
- `#part/<teamId>/<partId>` — part detail (also opens as bottom sheet
  on car view)

## Part data model (12 parts per car, 2026 specific)
Each part has:
- `name`, `description` (tappable insight)
- `regulation` (FIA 2026 Tech Regs article reference)
- `spec` (measurable spec: weight, dimensions, etc.)
- `impact` (telemetry-derived: how it affects lap time / race)
- `position` (x,y,z in 3D space, normalized 0-1)
- `mesh_hint` (which geometry primitive: box/cylinder/etc.)

Parts: Front Wing, Rear Wing, Floor, Sidepods, Halo, Nose, Suspension
(front/rear), Power Unit, Battery (MGU-K), Brake Duct, Mirror,
Diffuser.

## Verification checklist (BEFORE the subagent declares done)
1. [ ] `index.html` exists at project root, opens in browser
2. [ ] No console errors in browser dev tools
3. [ ] All 11 teams load from `./data/constructors.json`
4. [ ] All 22 drivers load from `./data/drivers.json`
5. [ ] R1-R5 results render correctly per team/driver
6. [ ] R6-R22 show as "UPCOMING" with date
7. [ ] 3D car renders for at least 1 team (Mercedes W17 baseline)
8. [ ] At least 4 parts are tappable on the 3D car, open detail
9. [ ] Smooth fade/slide between screens
10. [ ] Static server running, Tailscale-reachable on `:8081`
11. [ ] Public IP blocked (verify iptables rule)
12. [ ] Total HTML < 500KB (no asset bloat)
13. [ ] Mobile responsive (test 375px viewport)

## Out of scope
- Real CAD models (use stylized regulation-compliant geometry)
- Driver telemetry visualization (car + parts only)
- Race replay / lap-time playback
- Account / save state
- PWA / offline
- Backend / database
