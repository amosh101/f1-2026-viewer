# F1 2026 Viewer

> Interactive browser portal for the 2026 F1 regulation era — built as a
> **competitive-intelligence tool** for team engineers and strategists who need
> a fast read on rivals' pace, parts, reliability, qualifying, and teammate
> deltas.

**Live (Tailscale only):** `http://100.91.143.50:8081/`
**Public access:** blocked by design (iptables rule on the box).

## Pages

| Page | File | Size | Purpose |
|---|---|---|---|
| Home | `index.html` | 114 KB | Live season summary, team grid, season-action buttons |
| SVG car viewer | `explore-car.html` | 19 KB | Tap 12 parts, see FIA 2026 Tech Regs citation + impact |
| Part changes | `part-changes.html` | 11 KB | Tracked team upgrades R1 → latest (3 hand-curated) |
| Car issues | `car-issues.html` | 11 KB | Mechanical DNFs across 11 teams (24 documented) |
| Pace dashboard | `pace.html` | 20 KB | Engineer view: race pace, teammate delta, qualifying gap |
| Regulations | `regulations.html` | 15 KB | Year-on-year FIA regulation changes (2025, 2026) |

## What's real (no mocks)

- **11 constructors** — Mercedes, Ferrari, Red Bull, McLaren, Aston Martin,
  Alpine, Williams, RB, Audi, Haas, Cadillac (Audi + Cadillac are 2026 entries)
- **22 drivers** with permanent numbers, nationalities, DOBs
- **6 races completed** (R1 Australia → R6 Monaco), **16 upcoming** (R7-R22)
- **Championship live**: Antonelli 156 PTS / Mercedes, ~2 wins/race average
- **12 car parts** mapped to FIA 2026 Technical Regulations articles
  (3.7, 3.9, 3.10, 3.13, 3.14, 3.15, 5, 5.4, 10, 11, 12)
- **14 regulation changes** documented for 2026 across 4 categories
  (aero, power unit, chassis, sporting)
- **24 mechanical DNFs** across 11 teams, R1-R6
- **Race pace + teammate deltas** computed from real race data, R1-R6
- **Regulation rewrite headline**: +70% (FIA: "the most comprehensive rules
  overhaul in four decades")

## What we deliberately don't have

- **Telemetry** (speed/throttle/brake/tyre temp channels) — OpenF1's
  telemetry endpoints (`/laps`, `/stints`, `/pit`) 404 for all 2026 session
  keys. Documented on `pace.html` methodology block.
- **Onboard video analysis** — F1 copyrighted all onboard footage. Would
  require AWS Fan Vision partnership or aggressive F1 TV Pro scraping.
- **Auto-scraped part changes** — 3 hand-curated entries from The Race.
  Press-release or media keyword scrape planned but not built.
- **Driver quotes** — 24 quotes from The Race articles are cached in session
  memory but not yet surfaced (planned for a future Driver page).

## File layout

```
f1-2026-viewer/
├── README.md              # this file
├── SPEC.md                # original design spec
├── BUILD-REPORT.md        # current shipped state
├── ARCHITECTURE.md        # data flow + design decisions
├── ROADMAP.md             # what we're building next
├── DATA-REFERENCE.md      # JSON schemas for every data file
├── OPERATIONS.md          # server, cron, tests, iPhone workflow
├── .gitignore
├── index.html             # 114 KB, home + team detail + nav logic
├── explore-car.html       # 19 KB, SVG car + 12 part hotspots
├── part-changes.html      # 11 KB
├── car-issues.html        # 11 KB
├── pace.html              # 20 KB, engineer dashboard
├── regulations.html       # 15 KB
├── vendor/three.module.js # 1.27 MB Three.js (legacy, not loaded by home)
├── data/                  # 540 KB JSON caches
│   ├── latest.json                    # pointer to current round
│   ├── season-summary.json            # 6 rounds summary
│   ├── regulations.json               # 15 FIA changes, 2 years
│   ├── pace-dashboard.json            # 133 KB, 11 teams × 6 rounds × 2 drivers
│   ├── part-changes.json              # 3 hand-curated entries
│   ├── car-issues-dnf.json            # 24 DNFs
│   ├── constructors.json              # 11 teams, names/colors
│   ├── drivers.json                   # 22 drivers
│   ├── driver-team-map.json
│   ├── helmets.json                   # helmet colors per driver
│   ├── driver-standings-r6.json       # 22-driver championship
│   ├── constructor-standings-r6.json  # 11-team championship
│   ├── openf1-drivers-latest.json
│   ├── r1-australia.json ... r6-monaco.json        # 6 race result files
│   └── r1-australia-qualifying.json ... r6-monaco-qualifying.json  # 6 qualifying files
└── scripts/
    ├── update_f1_data.py       # 19 KB, weekly cron: race + standings + pace
    ├── build_issue_data.py     # 7 KB, derives car-issues-dnf.json
    ├── derive_pace.py          # 16 KB, derives pace-dashboard.json
    ├── update_regulations.py   # 8 KB, yearly: validate / add-year / summary
    ├── test-*.js               # Playwright iOS WebKit test suite
    └── shot-*.js               # screenshot scripts for visual verification
```

## Run locally

```bash
# Tailscale-only static server (matches prod)
python3 -m http.server 8081 --bind 100.91.143.50

# or for local dev (will hang on 100.91.143.50 from outside Tailscale)
python3 -m http.server 8081 --bind 127.0.0.1
```

No build step, no node_modules. All dependencies (Inter, Three.js) loaded
from CDN. Data is read from `data/*.json` at runtime — refresh those, the
site updates.

## Tests

Playwright iOS WebKit test suite in `scripts/test-*.js`. The reference
installation is at `/root/.npm/_npx/e41f203b7505f1fb/node_modules/playwright`.

```bash
node scripts/test-regulations.js          # regulations page + REG REWRITE button
node scripts/test-season-buttons.js       # 3 season-action buttons
node scripts/test-home-stats.js           # 4 stat cards
node scripts/test-detail-pages.js         # part-changes + car-issues drill-down
node scripts/test-nav-loop.js             # back/forward navigation
node scripts/test-home-layout.js          # 4-stat layout, no horizontal overflow
```

## Related docs

- **`ARCHITECTURE.md`** — data flow, the Sunday cron pipeline, design decisions
- **`ROADMAP.md`** — 4 priority tiers of what to build next, with effort estimates
- **`DATA-REFERENCE.md`** — JSON schemas, fields, where each value comes from
- **`OPERATIONS.md`** — server management, cron, debugging, iPhone verification
- **`BUILD-REPORT.md`** — current verified-working state
- **`SPEC.md`** — original design spec (kept for historical reference)

## License

Data is public (Jolpica/Ergast + The Race / FIA citations). Code: MIT.
