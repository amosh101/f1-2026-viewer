# F1 2026 Viewer — Build Report

**Built:** 2026-06-07
**URL:** `http://100.91.143.50:8081/` (Tailscale-only, public IP blocked)
**File:** `/root/.hermes/workspace/projects/f1-2026-viewer/index.html`
**Size:** 76 KB single self-contained file (2,484 lines)

## What shipped

A single self-contained HTML file with embedded CSS and inline ES module
JS. Three.js loaded from `https://esm.sh/three@0.160.0`. Inter from
Google Fonts. No build step, no node_modules, no external app code.

## Verified working (real test output, not mock)

| Screen | Verified |
|---|---|
| Splash (1.4s auto-dismiss) | ✓ advanced to teams, "A NEW ERA OF FORMULA 1" copy |
| Teams grid | ✓ 11 team cards, each with name + nationality + lead driver + team-color stripe |
| Team detail | ✓ Mercedes clicked → crest colored `#00D7B6` (teal), 2 driver cards (Antonelli #12, Russell #63) with helmets, 161 team points computed from podium data |
| 3D car view | ✓ Three.js WebGL canvas 832×418, Mercedes colored, 13 tappable parts, parts panel populated |
| Part detail | ✓ Rear Wing clicked → sheet opens with FIA Art. 3.10, "+15–20 km/h on straights in Z-Mode" impact note, Ferrari red `rgb(220, 0, 0)` tag, 4 spec rows |
| Season strip | ✓ 22 race cards, 5 with podium data, R6 Monaco marked NEXT, R7-R22 marked UPCOMING |
| Back navigation | ✓ team → car → sheet close → back to team, all smooth |

## Real data driving the app (no mocks)

- **11 constructors** from Jolpica/Ergast 2026
- **22 drivers** with permanent numbers, nationalities, DOBs (ages computed)
- **Driver → team mapping** built from R5 results (full 22/22 mapped)
- **5 completed races** with podiums (R1 Australia through R5 Canada)
- **R6-R22** marked as upcoming (R6 Monaco is next, R7-R22 after)
- **Live stat: leader** computed by counting P1 finishes (Antonelli 4, Russell 1)
- **Team points** summed from podium positions (Mercedes 161, etc.)
- **2026 FIA Tech Regs articles** cited per part (3.7, 3.9, 3.10, 3.13, 3.14, 3.15, 5, 5.4, 10, 11, 12)

## 3D car (regulation-correct 2026 baseline)

13 named parts as Three.js BoxGeometry primitives, positioned to
represent a regulation-correct 2026 chassis. Team color applied to
front wing, rear wing, sidepods, nose, and diffuser. Shadow-mapped
3-point lighting (key + rim + fill) for cinematic look. 4 wheel
cylinders (not part of the 12 tappable). Auto-rotate when idle, drag
to orbit, scroll to zoom, hover highlights part (emissive), click
opens bottom sheet.

| Part | Position (x,y,z) | FIA Reg | Impact note |
|---|---|---|---|
| Front Wing | (-2.0, 0, 0) | Art. 3.9 | 2-element cascade, narrower than 2024 |
| Rear Wing | (1.9, 0.45, 0) | Art. 3.10 | Active aero X-Mode + Z-Mode, replaces DRS |
| Floor | (0, -0.3, 0) | Art. 3.13 | Edge-wing, stronger ground effect |
| L/R Sidepods | (0, 0.15, ±0.75) | Art. 3.15 | Slimmer, new side intrusion panels |
| Halo | (-0.3, 0.65, 0) | Art. 12 | Titanium, 9.5 kg FIA minimum |
| Nose | (-1.6, 0.15, 0) | Art. 3.7 | Slimmer, integrated with front wing |
| Front/Rear Suspension | ±(0.9/1.3, 0.25, 0.5) | Art. 10 | Push-rod or pull-rod allowed |
| Power Unit | (0.4, 0.1, 0) | Art. 5 | 1.6L V6 + 50% electric MGU-K |
| Battery / MGU-K | (0, 0.4, 0) | Art. 5.4 | ~120 kW deployed per lap |
| Brake Duct | (-0.9, 0.05, 0.5) | Art. 11 | Critical for tyre management |
| Diffuser | (1.9, -0.2, 0) | Art. 3.14 | Wider, more aggressive ramp |

## Design system

- **Style:** SpaceX-inspired cinematic dark (pure `#000` + spectral
  `#f0f0fa`), uppercase + 0.12-0.25em letter-spacing, ghost buttons
  with `rgba(240,240,250,0.06)` background, 32px radius, 18px padding
- **Type:** Inter (CDN), 300/400/500/600/700/800 weights
- **Motion:** 180-320ms cubic-bezier(0.22, 0.61, 0.36, 1) easings,
  `prefers-reduced-motion` respected
- **Responsive:** breakpoints at 960px and 560px, mobile-first grids

## File layout

```
f1-2026-viewer/
├── SPEC.md              # design + scope spec
├── README.md            # run instructions
├── BUILD-REPORT.md      # this file
├── index.html           # 76KB, the entire app
├── data/                # real JSON caches (still served for transparency)
│   ├── constructors.json
│   ├── drivers.json
│   ├── driver-team-map.json
│   ├── season-2026.json
│   ├── season-summary.json
│   ├── r1-australia.json ... r5-canada.json
│   ├── r5-canada-qualifying.json
│   └── openf1-drivers-latest.json
└── assets/, public/, src/  # empty, kept for future expansion
```

## How to use

```bash
# Server already running on Tailscale
open http://100.91.143.50:8081/
# or from this box
curl http://100.91.143.50:8081/
```

Server PID 69591 (background, monitored by terminal). iptables rule
present: `tcp dpt:8081 !s 100.64.0.0/10 → DROP`. 8 packets dropped
from public IP since launch.

## SPEC.md verification checklist

- [x] index.html opens in browser without console errors
- [x] All 5 screens (splash → teams → team → car → part) work
- [x] All 11 teams render
- [x] Drivers display with number, name, team
- [x] 3D car renders with 13 named parts
- [x] Parts clickable, open detail sheet
- [x] R1-R5 show results, R6-R22 show as UPCOMING with date
- [x] Smooth transitions between screens (200-300ms)
- [x] Team color applied to 3D car
- [x] prefers-reduced-motion handled
- [x] Mobile responsive (CSS verified at 960px / 560px breakpoints)
- [x] No "lorem ipsum" or fake data
- [x] HTML < 500KB (76KB)

## Open follow-ups (for v2)

1. iOS port: SwiftUI + RealityKit, then Reality Composer Pro for
   per-team geometry
2. Real per-driver setup data (not in public APIs, would need
   partnership or licensed feed)
3. Telemetry overlay (OpenF1 has car_data at 4Hz per car)
4. On-demand asset loading (current is fine for 1 car, will bloat
   when all 11 teams get unique geometries)
5. Mobile 3D performance tuning (currently fine on desktop Chrome,
   needs to be tested on iPhone 12+)
6. Audio (engine sound, requires licensing — defer)
