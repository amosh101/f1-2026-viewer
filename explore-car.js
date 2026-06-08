/* explore-car.js — F1 2026 Explore the Car
 * Standalone, no build step, no WebGL, no Three.js.
 * Real team data (11 constructors, 2026 chassis names verified via Wikipedia 2026
 * F1 season page), real driver-team map, real R1-R6 race results (Jolpica/Ergast).
 *
 * Sections:
 *  - TEAMS: constructor metadata + 2026 livery colors (visual best-estimate for
 *    the team color stripe; primary navy/red/paper etc. per publicly known liveries)
 *  - PARTS: 12 regulation parts with FIA 2026 Tech Regs article + impact note
 *  - SEASON: R1 Australia → R6 Monaco, real podiums + dates
 *  - STANDINGS: real driver + constructor points as of R6
 */

const TEAMS = [
  { id: "mercedes",     name: "Mercedes",          chassis: "F1 W17",  primary: "#27e0c4", secondary: "#0a0a0a" },
  { id: "ferrari",      name: "Ferrari",           chassis: "SF-26",   primary: "#dc0000", secondary: "#ffeb00" },
  { id: "red_bull",     name: "Red Bull",          chassis: "RB22",    primary: "#1e3a8a", secondary: "#dc0000" },
  { id: "mclaren",      name: "McLaren",           chassis: "MCL40",   primary: "#ff8000", secondary: "#0066cc" },
  { id: "aston_martin", name: "Aston Martin",      chassis: "AMR26",   primary: "#00665e", secondary: "#ffcc00" },
  { id: "alpine",       name: "Alpine F1 Team",    chassis: "A526",    primary: "#0090d4", secondary: "#ff5fa2" },
  { id: "williams",     name: "Williams",          chassis: "FW48",    primary: "#005aff", secondary: "#ffffff" },
  { id: "rb",           name: "RB F1 Team",        chassis: "VCARB 03",primary: "#1634a3", secondary: "#c8102e" },
  { id: "audi",         name: "Audi",              chassis: "R26",     primary: "#bb0a30", secondary: "#000000" },
  { id: "haas",         name: "Haas F1 Team",      chassis: "VF-26",   primary: "#9c9c9c", secondary: "#ed1c24" },
  { id: "cadillac",     name: "Cadillac F1 Team",  chassis: "MAC-26",  primary: "#1c3a72", secondary: "#c9a96e" }
];

// Driver → team map (real 2026 lineup, verified via driver-team-map.json)
const DRIVERS = {
  mercedes:     [{ name: "Antonelli", num: 12 }, { name: "Russell", num: 63 }],
  ferrari:      [{ name: "Hamilton",  num: 44 }, { name: "Leclerc", num: 16 }],
  red_bull:     [{ name: "Verstappen",num: 1  }, { name: "Hadjar",  num: 6  }],
  mclaren:      [{ name: "Norris",    num: 4  }, { name: "Piastri", num: 81 }],
  aston_martin: [{ name: "Alonso",    num: 14 }, { name: "Stroll",  num: 18 }],
  alpine:       [{ name: "Gasly",     num: 10 }, { name: "Colapinto",num: 43}],
  williams:     [{ name: "Sainz",     num: 55 }, { name: "Albon",   num: 23 }],
  rb:           [{ name: "Lawson",    num: 30 }, { name: "Lindblad",num: 41 }],
  audi:         [{ name: "Hulkenberg",num: 27 }, { name: "Bortoleto",num: 5 }],
  haas:         [{ name: "Ocon",      num: 31 }, { name: "Bearman", num: 87 }],
  cadillac:     [{ name: "Bottas",    num: 77 }, { name: "Perez",   num: 11 }]
};

// Constructor standings (real, after R6 Monaco 2026-06-07)
const STANDINGS = {
  mercedes:     { pos: 1,  pts: 244, wins: 6 },
  ferrari:      { pos: 2,  pts: 165, wins: 0 },
  mclaren:      { pos: 3,  pts: 118, wins: 0 },
  red_bull:     { pos: 4,  pts: 72,  wins: 0 },
  alpine:       { pos: 5,  pts: 41,  wins: 0 },
  rb:           { pos: 6,  pts: 39,  wins: 0 },
  haas:         { pos: 7,  pts: 21,  wins: 0 },
  williams:     { pos: 8,  pts: 11,  wins: 0 },
  audi:         { pos: 9,  pts: 2,   wins: 0 },
  aston_martin: { pos: 10, pts: 1,   wins: 0 },
  cadillac:     { pos: 11, pts: 0,   wins: 0 }
};

// 12 parts. Coordinates are in the SVG's viewBox (0..1000 × 0..600).
// regulation = FIA 2026 Technical Regulations article (publicly known ref),
// spec = measurable spec, impact = how it affects lap time / race.
const PARTS = [
  { id: "frontWing", name: "Front Wing",        x: 75,  y: 300, regulation: "FIA Tech Regs Art. 3.9",  spec: "2-element cascade, narrower than 2024.",            impact: "Sets front-end aero balance. ~30% of total drag comes from here. 2026 regs move the inwash toward the floor to feed the underbody." },
  { id: "nose",      name: "Nose Cone",         x: 145, y: 300, regulation: "FIA Tech Regs Art. 3.7",  spec: "Slimmer, lower, integrated with the front wing.",    impact: "Reduces drag and improves airflow to the floor edge — a major gain for 2026." },
  { id: "sidepods",  name: "Sidepods",          x: 360, y: 300, regulation: "FIA Tech Regs Art. 3.15", spec: "Slimmer than 2024, new side-intrusion panels (L+R).",  impact: "Less drag, cooling duties shift to the floor. The McLaren-style tapered sidepod is no longer legal under 2026 rules." },
  { id: "floor",     name: "Floor",             x: 500, y: 320, regulation: "FIA Tech Regs Art. 3.13", spec: "Edge-wing style, stronger ground effect.",            impact: "Primary downforce source. 2026 cars are ~30 kg lighter overall but generate similar total downforce to 2024 — the floor does the work." },
  { id: "halo",      name: "Halo",              x: 500, y: 300, regulation: "FIA Tech Regs Art. 12",   spec: "Titanium, FIA-mandated minimum 9.5 kg.",               impact: "Survival cell. Mandated since 2018. No aero effect. 2026 integrates the headrest fairing into the halo ring." },
  { id: "powerUnit", name: "Power Unit",        x: 625, y: 320, regulation: "FIA Tech Regs Art. 5",    spec: "1.6L V6 turbo + 50% electric MGU-K (350 kW cap).",     impact: "Total ~1000 HP equivalent. New 50/50 ICE-electric split: ~550 HP from the V6, ~450 HP from the K. Big change for strategy." },
  { id: "battery",   name: "Battery / MGU-K",   x: 510, y: 300, regulation: "FIA Tech Regs Art. 5.4",  spec: "Lithium-ion, higher energy density for 50% electric.", impact: "Powers the MGU-K. ~120 kW deployed per lap. Recovery zones on straights, deployment on corner exit." },
  { id: "suspF",     name: "Front Suspension",  x: 200, y: 220, regulation: "FIA Tech Regs Art. 10",   spec: "Push-rod or pull-rod allowed.",                       impact: "Affects front-end feel and the wake the floor sees. Mercedes and Red Bull are known pull-rod users." },
  { id: "suspR",     name: "Rear Suspension",   x: 760, y: 220, regulation: "FIA Tech Regs Art. 10",   spec: "Pull-rod preferred for low centre of gravity.",       impact: "Affects rear stability and diffuser flow. Pull-rod is aerodynamically superior for 2026 regs." },
  { id: "brakeDuct", name: "Brake Duct",        x: 235, y: 300, regulation: "FIA Tech Regs Art. 11",   spec: "Integrated with bodywork, regulates brake temp.",      impact: "Critical for tyre management. 2026 cars run hotter brakes to keep tyre temps in the operating window." },
  { id: "diffuser",  name: "Diffuser",          x: 760, y: 300, regulation: "FIA Tech Regs Art. 3.14", spec: "Wider, more aggressive ramp angles.",                 impact: "Extracts underfloor airflow, adds downforce at speed. 2026 regs allow taller diffuser entries for more aggressive ramp angles." },
  { id: "rearWing",  name: "Rear Wing",         x: 840, y: 300, regulation: "FIA Tech Regs Art. 3.10", spec: "Active aero: X-Mode (high downforce) + Z-Mode (low drag).", impact: "+15–20 km/h on straights in Z-Mode. X-Mode for high-downforce sectors. Replaces DRS from 2024." }
];

// 2026 season results (R1-R6, real from Jolpica / Ergast 2026-06-08)
const SEASON = [
  { r: 1, name: "Australian Grand Prix",   date: "2026-03-08", circuit: "Albert Park",                  podium: [
    { pos: 1, driver: "Russell",    team: "Mercedes" },
    { pos: 2, driver: "Antonelli",  team: "Mercedes" },
    { pos: 3, driver: "Leclerc",    team: "Ferrari"  }
  ]},
  { r: 2, name: "Chinese Grand Prix",      date: "2026-03-15", circuit: "Shanghai International",      podium: [
    { pos: 1, driver: "Antonelli",  team: "Mercedes" },
    { pos: 2, driver: "Russell",    team: "Mercedes" },
    { pos: 3, driver: "Hamilton",   team: "Ferrari"  }
  ]},
  { r: 3, name: "Japanese Grand Prix",     date: "2026-03-29", circuit: "Suzuka",                       podium: [
    { pos: 1, driver: "Antonelli",  team: "Mercedes" },
    { pos: 2, driver: "Piastri",    team: "McLaren"  },
    { pos: 3, driver: "Leclerc",    team: "Ferrari"  }
  ]},
  { r: 4, name: "Miami Grand Prix",        date: "2026-05-03", circuit: "Miami International Autodrome",podium: [
    { pos: 1, driver: "Antonelli",  team: "Mercedes" },
    { pos: 2, driver: "Norris",     team: "McLaren"  },
    { pos: 3, driver: "Piastri",    team: "McLaren"  }
  ]},
  { r: 5, name: "Canadian Grand Prix",     date: "2026-05-24", circuit: "Circuit Gilles Villeneuve",    podium: [
    { pos: 1, driver: "Antonelli",  team: "Mercedes" },
    { pos: 2, driver: "Hamilton",   team: "Ferrari"  },
    { pos: 3, driver: "Verstappen", team: "Red Bull" }
  ]},
  { r: 6, name: "Monaco Grand Prix",       date: "2026-06-07", circuit: "Circuit de Monaco",            podium: [
    { pos: 1, driver: "Antonelli",  team: "Mercedes" },
    { pos: 2, driver: "Hamilton",   team: "Ferrari"  },
    { pos: 3, driver: "Hadjar",     team: "Red Bull" }
  ]}
];

/* ===== State + helpers ===== */
const state = { team: "mercedes", active: null };

function teamById(id) { return TEAMS.find(t => t.id === id); }

function applyTeamLivery(team) {
  // Update the team-color gradient in the SVG so the sidepods, wings, etc.
  // reflect the current constructor's livery.
  const svg = document.querySelector('.car-wrap svg');
  if (!svg) return;
  const gradA = svg.querySelector('#teamGradA');
  const gradB = svg.querySelector('#teamGradB');
  if (gradA) gradA.setAttribute('stop-color', team.secondary || '#0e0e14');
  if (gradB) gradB.setAttribute('stop-color', team.primary   || '#27e0c4');
  // Set CSS var so the active part uses team accent
  document.documentElement.style.setProperty('--accent', team.primary);
}

function renderTeamChips() {
  const root = document.getElementById('teams');
  root.innerHTML = TEAMS.map(t => `
    <button class="team-chip ${t.id === state.team ? 'active' : ''}" data-team="${t.id}" aria-label="${t.name} ${t.chassis}">
      <span class="stripe" style="background:${t.primary}"></span>
      <div class="name">${t.name}</div>
      <div class="chassis">${t.chassis}</div>
    </button>
  `).join('');
  root.querySelectorAll('.team-chip').forEach(btn => {
    btn.addEventListener('click', () => selectTeam(btn.dataset.team));
  });
}

function renderHero(team) {
  document.getElementById('teamLabel').textContent   = team.name.toUpperCase();
  document.getElementById('chassisLabel').textContent = team.chassis;
  const s = STANDINGS[team.id];
  document.getElementById('ptsLabel').innerHTML =
    s ? `P${s.pos} · <b>${s.pts}</b> pts` : `P— · <b>—</b> pts`;
}

function renderHotspots() {
  const g = document.getElementById('hotspots');
  g.innerHTML = PARTS.map((p, i) => `
    <g class="hot-group" data-part="${p.id}">
      <circle class="hot" cx="${p.x}" cy="${p.y}" r="8"
              fill="rgba(0,0,0,0.6)" stroke="var(--accent)" stroke-width="2"/>
      <text class="hot-num" x="${p.x}" y="${p.y + 3}" text-anchor="middle"
            font-size="9" font-weight="700" fill="var(--accent)" font-family="-apple-system,system-ui,sans-serif">${i+1}</text>
    </g>
  `).join('');
  g.querySelectorAll('.hot-group').forEach(node => {
    node.style.cursor = 'pointer';
    node.addEventListener('click', () => openPartSheet(node.dataset.part));
  });
}

function renderPartsList() {
  const root = document.getElementById('partsList');
  root.innerHTML = PARTS.map((p, i) => `
    <div class="part-row" data-part="${p.id}" role="button" tabindex="0">
      <div class="num">${i+1}</div>
      <div class="label">
        <div class="name">${p.name}</div>
        <div class="reg">${p.regulation}</div>
      </div>
      <div class="chev">›</div>
    </div>
  `).join('');
  root.querySelectorAll('.part-row').forEach(row => {
    row.addEventListener('click', () => openPartSheet(row.dataset.part));
    row.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        openPartSheet(row.dataset.part);
      }
    });
  });
}

function renderSeason() {
  const root = document.getElementById('seasonList');
  const selTeam = state.team;
  const selName = teamById(selTeam).name;
  root.innerHTML = SEASON.map(race => {
    const teamInPodium = race.podium.find(p => p.team.toLowerCase().replace(/\s+/g,'_').includes(selTeam.replace(/_/g,'')) || p.team === teamById(selTeam).name);
    const teamPos = teamInPodium ? ` <b>P${teamInPodium.pos}</b> ${teamInPodium.driver}` : '';
    return `
      <div class="race-row">
        <div class="r">R${race.r}</div>
        <div>
          <div class="name">${race.name} <span class="date">· ${race.date}</span></div>
          <div class="date">${race.circuit}</div>
          <div class="podium">${race.podium.map(p => `P${p.pos} ${p.driver}`).join(' · ')}${teamPos ? ' · ' + selName + teamPos : ''}</div>
        </div>
      </div>
    `;
  }).join('');
}

function openPartSheet(partId) {
  const p = PARTS.find(x => x.id === partId);
  if (!p) return;
  state.active = partId;
  document.getElementById('sheetName').textContent  = p.name;
  document.getElementById('sheetReg').textContent   = p.regulation;
  document.getElementById('sheetSpec').textContent  = p.spec;
  document.getElementById('sheetImpact').innerHTML  = '<b>Why it matters:</b> ' + p.impact;
  document.getElementById('sheet').classList.add('open');
  document.getElementById('scrim').classList.add('open');
  // Highlight the matching parts-list row
  document.querySelectorAll('.part-row').forEach(r => {
    r.classList.toggle('active', r.dataset.part === partId);
  });
}

function closePartSheet() {
  state.active = null;
  document.getElementById('sheet').classList.remove('open');
  document.getElementById('scrim').classList.remove('open');
  document.querySelectorAll('.part-row').forEach(r => r.classList.remove('active'));
}

function selectTeam(teamId) {
  state.team = teamId;
  state.active = null;
  const t = teamById(teamId);
  applyTeamLivery(t);
  renderHero(t);
  renderSeason();
  // Update chip selection
  document.querySelectorAll('.team-chip').forEach(c => {
    c.classList.toggle('active', c.dataset.team === teamId);
  });
  // If the sheet is open, close it (different team → different context)
  closePartSheet();
  // Scroll the team chip into view (mobile horizontal scroll)
  const active = document.querySelector(`.team-chip[data-team="${teamId}"]`);
  if (active) active.scrollIntoView({ behavior: 'smooth', inline: 'center', block: 'nearest' });
}

/* ===== Boot ===== */
function getInitialTeam() {
  // Honor ?team=<id> query string (deep link from the team-detail screen
  // in index.html). Falls back to 'mercedes' if missing or unknown.
  const params = new URLSearchParams(window.location.search);
  const t = params.get('team');
  if (t && TEAMS.find(x => x.id === t)) return t;
  return 'mercedes';
}

document.addEventListener('DOMContentLoaded', () => {
  renderTeamChips();
  renderHotspots();
  renderPartsList();
  selectTeam(getInitialTeam());  // also applies livery, renders hero, season
  renderSeason();                // safe to call again — idempotent

  document.getElementById('sheetClose').addEventListener('click', closePartSheet);
  document.getElementById('scrim').addEventListener('click', closePartSheet);

  // ESC closes the sheet
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closePartSheet();
  });
});
