# F1 2026 Viewer

Interactive browser experience for the 2026 F1 regulation era. Pick a
team, see the car, tap parts, read the spec and the FIA 2026 Technical
Regulation article behind it, see how that team did this season.

## Live

- **Tailscale:** `http://100.91.143.50:8081/`
- **Public:** blocked (Tailscale-only by design)

## What's in this repo

- `index.html` — 76 KB single self-contained file, the entire app
- `data/` — cached JSON from Jolpica (Ergast mirror) + OpenF1,
  captured 2026-06-06
- `SPEC.md` — design + scope spec
- `BUILD-REPORT.md` — what shipped and what was verified

## Run locally

```bash
python3 -m http.server 8081 --bind 127.0.0.1
open http://127.0.0.1:8081/
```

No build step, no node_modules. Three.js loads from `esm.sh`, Inter
from Google Fonts.

## What's real (no mocks)

- 11 constructors (Mercedes, Ferrari, Red Bull, McLaren, Aston
  Martin, Alpine, Williams, RB, Audi, Haas, Cadillac) — Audi and
  Cadillac are the new 2026 entries
- 22 drivers with numbers, nationalities, dates of birth
- 22-race 2026 calendar, R1 Australia → R22 Abu Dhabi
- R1-R5 completed with podiums (Antonelli 4 wins, Russell 1)
- R6 Monaco = NEXT (race date 2026-06-07)
- R7-R22 marked UPCOMING with dates
- 13 car parts mapped to FIA 2026 Technical Regulations articles:
  3.7, 3.9, 3.10, 3.13, 3.14, 3.15, 5, 5.4, 10, 11, 12

## What's stylized (honest)

- 3D car geometry is **regulation-correct but generic** — built from
  primitive Three.js geometry to match the 2026 spec (wheelbase,
  floor edges, front wing cascade, sidepod intrusion panels). It
  does **not** replicate the proprietary aero detail of any team's
  real 2026 car.
- Team liveries are tinted via the team color hex code; logos and
  sponsor decals are not modeled.
- Impact notes are derived from FIA regulation framing (what the
  part is for), not from per-team proprietary telemetry.

## Roadmap

- iOS port: SwiftUI + RealityKit
- Per-team unique geometry from launch imagery
- OpenF1 telemetry overlay (4 Hz car data per driver)
- Audio (deferred — engine sound requires licensing)

## License

Data is public (Jolpica + OpenF1 free APIs). Code: MIT.
