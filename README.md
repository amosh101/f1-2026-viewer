# F1 2026 Viewer — Browser MVP

Interactive browser experience for the 2026 F1 regulation era.
Built as a single-page HTML application with Three.js for 3D car
visualization, real 2026 data from Jolpica + OpenF1 APIs.

## Run

```bash
cd /root/.hermes/workspace/projects/f1-2026-viewer
python3 -m http.server 8081 --bind 100.91.143.50
```

Then open: `http://100.91.143.50:8081/`

Tailscale-only — public IP blocked via iptables.

## Layout

```
.
├── SPEC.md                  # design + scope spec
├── README.md
├── index.html               # the entire app
├── data/                    # pre-cached API responses (real, no mocks)
│   ├── season-2026.json
│   ├── constructors.json
│   ├── drivers.json
│   ├── r1-australia.json ... r5-canada.json
│   ├── r5-canada-qualifying.json
│   └── openf1-drivers-latest.json
└── assets/                  # if needed
```

## Data

All data fetched live from:
- `https://api.jolpi.ca/ergast/f1/2026/...` (Ergast mirror)
- `https://api.openf1.org/v1/...`

Snapshot taken 2026-06-06. Season has 5 races completed, R6 Monaco
is on 2026-06-07. R6-R22 show as UPCOMING.

## Refresh data

```bash
./scripts/refresh-data.sh
```

(To be added in v2.)

## iOS port

After browser MVP validates, port to SwiftUI + RealityKit. See
`SPEC.md` §"Scope deferred to v2".
