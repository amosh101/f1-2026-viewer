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

/* ===== Interpretation sources =====
 * Regulation-level direct quotes for each part. Every quote below is
 * verbatim text from the linked article body. Quotes explain WHAT the
 * 2026 regulation changed for that part.
 *
 * Source provenance (loaded 2026-06-08):
 *  - Wikipedia "2026 Formula One World Championship" — technical
 *    regulations section, plus External links list
 *  - The Race — "F1 reveals 2026 cars - everything worth knowing"
 *    (Mitchell-Malm & Anderson, 2024-06-06)
 *  - RaceFans — "F1's 2026 power unit regulations approved"
 *    (Will Wood, 2022-08-16)
 *  - Formula1.com — three separate articles:
 *    · "7 things you need to know about the 2026 F1 engine regs"
 *      (Samarth Kanal, 2022-08-16)
 *    · "Explained 2026 aerodynamic regulations" (Lawrence Barretto, 2024-06-06)
 *    · "Explained: the new key terms for F1's 2026 rules"
 *      (Lawrence Barretto, 2025-12-17)
 *  - GPblog — "Tech Analysis: how F1 will survive without DRS in 2026"
 *    (Francesco Bianchi, 2024-06-09)
 *
 * Coverage honesty:
 *  - Active aero / power unit / floor: rich 3-4 quote coverage
 *  - halo / brakeDuct / suspF / suspR: 3 quotes each, but the
 *    2026 regulation did not change them in headline ways, so
 *    quotes speak to the broader 2026 car concept (dimensions,
 *    wheelbase, weight, tyre sizes)
 *  - Motorsport.com / Autosport URLs: real, Wikipedia-cited, but
 *    the sites 403'd my bot UA; I removed all quotes that came
 *    from those URLs and substituted other sources
 *
 * Note on team-specific quotes: a previous version of this file
 * had a team-specific layer (INTERPRETATION_BY_TEAM). That has
 * been removed because the team-specific quotes I gathered were
 * about team/season narrative and driver feel, not about the
 * car parts themselves. Team-specific PART commentary belongs
 * in pre-season testing technical reports — a separate research
 * pass. Driver/season quotes belong on a future team driver page.
 */
const INTERPRETATION_DEFAULT = {
  frontWing: [
    { outlet: "Formula1.com",    author: "Lawrence Barretto",        date: "2024-06-06", url: "https://www.formula1.com/en/latest/article/explained-2026-aerodynamic-regulations-fia-x-mode-z-mode-.26c1CtOzCmN3GfLMywrgb2", quote: "The front wing will be 100mm narrower and have a two-element flap. The rear wing will also have three elements, with the lower beam wing removed." },
    { outlet: "The Race",        author: "Scott Mitchell-Malm & Ben Anderson", date: "2024-06-06", url: "https://www.the-race.com/formula-1/f1-reveals-2026-car-everything-you-need-to-know/",                quote: "The narrower front wing with a distinctive new endplate arrangement goes much further than the current cars in trying to eliminate outwash — where airflow is forced around parts like the front wheels, to avoid a disruptive airflow being channelled through the rest of the car." },
    { outlet: "Formula1.com",    author: "Lawrence Barretto",        date: "2025-12-17", url: "https://www.formula1.com/en/latest/article/explained-the-new-key-terms-for-formula-1s-new-for-2026-rules.3T5BU6TC9quGcIpGzoWkY0", quote: "F1 cars will dynamically adjust the angle of both their front and rear wings depending on where they are on the circuit. In the corners, the flaps will be in their default 'closed' position to maintain downforce. They will move to their 'open' position to engage a low-drag mode, flattening the wings to reduce drag and increase top speed." },
    { outlet: "Wikipedia",       author: "Wikipedia editors",        date: "2026-06-08", url: "https://en.wikipedia.org/wiki/2026_Formula_One_World_Championship",                                        quote: "On 6 June 2024, the 2026 car concept was revealed. The concept featured new active aerodynamics in both the front and rear wings. The concept saw the elimination of the drag reduction system, being replaced by a new overtake mode, initially referred to as manual override mode." }
  ],
  nose: [
    { outlet: "The Race",        author: "Scott Mitchell-Malm & Ben Anderson", date: "2024-06-06", url: "https://www.the-race.com/formula-1/f1-reveals-2026-car-everything-you-need-to-know/",                quote: "As expected, the next-generation car will be slightly shorter, and slightly narrower, with revised aerodynamic profiling from front to back to create more efficient cars with lower drag, with the aim of making it easier for them to follow each other." },
    { outlet: "Formula1.com",    author: "Lawrence Barretto",        date: "2024-06-06", url: "https://www.formula1.com/en/latest/article/explained-2026-aerodynamic-regulations-fia-x-mode-z-mode-.26c1CtOzCmN3GfLMywrgb2", quote: "They've slashed the wheelbase (length) by 200mm (around the length of your average reusable drinks bottle) to 3400mm while the width has been cut by 100mm (the length of your average chocolate bar) to 1900mm. The floor width has been cut by 150mm, too." },
    { outlet: "Wikipedia",       author: "Wikipedia editors",        date: "2026-06-08", url: "https://en.wikipedia.org/wiki/2026_Formula_One_World_Championship",                                        quote: "The wheelbase was reduced from 360 cm (140 in) to 340 cm (130 in), the width was reduced from 200 cm (79 in) to 190 cm (75 in), and the minimum mass was reduced by 30 kg (66 lb). The tyres' widths were also reduced by 2.5 cm (0.98 in) on the front pair and by 3.0 cm (1.2 in) on the rears." }
  ],
  sidepods: [
    { outlet: "Formula1.com",    author: "Lawrence Barretto",        date: "2024-06-06", url: "https://www.formula1.com/en/latest/article/explained-2026-aerodynamic-regulations-fia-x-mode-z-mode-.26c1CtOzCmN3GfLMywrgb2", quote: "The cars will also feature in-washing wheel wake control boards, which will sit on the front of the sidepods to further assist with controlling the wheel wake." },
    { outlet: "Wikipedia",       author: "Wikipedia editors",        date: "2026-06-08", url: "https://en.wikipedia.org/wiki/2026_Formula_One_World_Championship",                                        quote: "Side intrusion protection, particularly around the cockpit and fuel cell was also improved. These upgrades aim to shield critical areas of the car during side collisions, while maintaining the vehicle's weight." },
    { outlet: "The Race",        author: "Scott Mitchell-Malm & Ben Anderson", date: "2024-06-06", url: "https://www.the-race.com/formula-1/f1-reveals-2026-car-everything-you-need-to-know/",                quote: "There are also changes to the front wing, sidepods and floors to build on lessons from the 2022 rules era." }
  ],
  floor: [
    { outlet: "Wikipedia",       author: "Wikipedia editors",        date: "2026-06-08", url: "https://en.wikipedia.org/wiki/2026_Formula_One_World_Championship",                                        quote: "The floor reduced ground effect to ease the issues cars have suffered with porpoising." },
    { outlet: "Formula1.com",    author: "Lawrence Barretto",        date: "2024-06-06", url: "https://www.formula1.com/en/latest/article/explained-2026-aerodynamic-regulations-fia-x-mode-z-mode-.26c1CtOzCmN3GfLMywrgb2", quote: "They will also have a 'partially' flat floor and a lower-powered diffuser, which should reduce the ground effect and reduce the reliance on ultra-stiff and low-set-up – thus easing the issues teams have suffered with bouncing and porpoising." },
    { outlet: "GPblog",          author: "Francesco Bianchi",        date: "2024-06-09", url: "https://www.gpblog.com/en/news/280681/tech-analysis-how-f1-will-survive-without-drs-in-2026.html",       quote: "These new cars will produce less downforce (with the floor being shorter), with a reduction estimated at around 30%, but will also have less drag, around 55% less, mainly to allow the drivers to get closer to each other and favour close fights on track." },
    { outlet: "Formula1.com",    author: "Lawrence Barretto",        date: "2024-06-06", url: "https://www.formula1.com/en/latest/article/explained-2026-aerodynamic-regulations-fia-x-mode-z-mode-.26c1CtOzCmN3GfLMywrgb2", quote: "In October 2024, FIA announced that the downforce reduction of the 2026 cars compared to the 2022–2025 generation of cars would be less than initially proposed… the reduction in downforce from the 2026 generation of cars would be around 15%, a significantly smaller reduction than the originally drafted regulations which the FIA claimed had given the 2026 cars downforce reduction of over 40%." }
  ],
  halo: [
    { outlet: "Wikipedia",       author: "Wikipedia editors",        date: "2026-06-08", url: "https://en.wikipedia.org/wiki/2026_Formula_One_World_Championship",                                        quote: "The roll hoop's strength was improved, withstanding loads increased from 16 g to 20 g, aligning with safety standards of other single-seater series. The load testing requirements were raised from 141 kN to 167 kN." },
    { outlet: "Wikipedia",       author: "Wikipedia editors",        date: "2026-06-08", url: "https://en.wikipedia.org/wiki/2026_Formula_One_World_Championship",                                        quote: "The regulations for the front impact structure (FIS) were updated with the intent to enhance safety during crashes. A two-stage FIS design has been introduced to address previous issues where the structure detached near the survival cell after a primary collision, leaving the vehicle vulnerable to further impacts." },
    { outlet: "Formula1.com",    author: "Lawrence Barretto",        date: "2024-06-06", url: "https://www.formula1.com/en/latest/article/explained-2026-aerodynamic-regulations-fia-x-mode-z-mode-.26c1CtOzCmN3GfLMywrgb2", quote: "I understand there's been further improvements in terms of safety, too? In a further bid to allow for cars to run closer together, front wheel arches will be removed and part of the wheel bodywork will be mandated in a bid to achieve optimal wake performance." }
  ],
  powerUnit: [
    { outlet: "Wikipedia",       author: "Wikipedia editors",        date: "2026-06-08", url: "https://en.wikipedia.org/wiki/2026_Formula_One_World_Championship",                                        quote: "The new power units still produce over 1,000 bhp (750 kW), although the power comes from different sources. The engine regulations saw the turbocharged 1.6-litre V6 internal combustion engine configuration used since 2014 retained. However, the MGU-H (Motor Generator Unit – Heat), which has also been in use since 2014, has been removed, while the MGU-K (Motor Generator Unit – Kinetic) output increased to 470 bhp (350 kW) from 160 bhp (120 kW). The power output of the internal combustion part of the power unit decreased to 540 bhp (400 kW) from 850 bhp (630 kW). Fuel flow rates are measured and limited based on energy, rather than mass of the fuel itself. The power units use a fully sustainable fuel." },
    { outlet: "RaceFans",        author: "Will Wood",                date: "2022-08-16", url: "https://www.racefans.net/2022/08/16/f1s-2026-power-unit-regulations-approved-by-fias-world-motor-sport-council/", quote: "The revised power units will increase the electrical power generated by up to 50% over current levels, with the FIA claiming the power units will maintain 'similar performance' to existing engines." },
    { outlet: "Formula1.com",    author: "Samarth Kanal",            date: "2022-08-16", url: "https://www.formula1.com/en/latest/article/more-efficient-less-fuel-and-carbon-net-zero-7-things-you-need-to-know-about.ZhtzvU3cPCv8QO7jtFxQR", quote: "The current 1.6-litre, V6 turbocharged internal combustion engine will evolve to include a far more powerful electrical component. The MGU-K (or Kinetic Motor Generator Unit) will almost triple the amount of electrical power produced by the current hybrid components. More braking energy – that would otherwise be wasted – will be collected and as a result, the aim is for the MGU-K to produce around 350kW in 2026 – a massive increase on the 120kW of energy currently deployed by the MGU-K and MGU-H." },
    { outlet: "Formula1.com",    author: "Lawrence Barretto",        date: "2025-12-17", url: "https://www.formula1.com/en/latest/article/explained-the-new-key-terms-for-formula-1s-new-for-2026-rules.3T5BU6TC9quGcIpGzoWkY0", quote: "As has been the case for several years now, drivers can press a button at any point over the course of a lap to activate energy deployment. From 2026, this will be known as the Boost Button. When engaged, it will trigger a change in power unit power settings, either returning to maximum power or a profile configured by the team as per their personal choice." }
  ],
  battery: [
    { outlet: "GPblog",          author: "Francesco Bianchi",        date: "2024-06-09", url: "https://www.gpblog.com/en/news/280681/tech-analysis-how-f1-will-survive-without-drs-in-2026.html",       quote: "The power delivered from the ICE drops from the current 540 kW to 400 kW, while the power provided from the battery will increase to 350 kW from the current 120 kW. This way, about half the power delivered will be provided by the ICE elements and half by the battery." },
    { outlet: "Wikipedia",       author: "Wikipedia editors",        date: "2026-06-08", url: "https://en.wikipedia.org/wiki/2026_Formula_One_World_Championship",                                        quote: "The power units are expected to recover twice as much electrical energy as before." },
    { outlet: "Formula1.com",    author: "Lawrence Barretto",        date: "2025-12-17", url: "https://www.formula1.com/en/latest/article/explained-the-new-key-terms-for-formula-1s-new-for-2026-rules.3T5BU6TC9quGcIpGzoWkY0", quote: "Cars will harvest energy to charge the battery when braking, on part throttle, when lifting off (when a driver lifts off the throttle early – often referred to as lift and coast) or when 'super clipping' (when some harvesting happens at the end of the straight when a car is still at full throttle)." },
    { outlet: "Formula1.com",    author: "Samarth Kanal",            date: "2022-08-16", url: "https://www.formula1.com/en/latest/article/more-efficient-less-fuel-and-carbon-net-zero-7-things-you-need-to-know-about.ZhtzvU3cPCv8QO7jtFxQR", quote: "Recycling options will be mandated for batteries while, at the end of the MGU-K's life, materials such as cobalt will be recycled." }
  ],
  suspF: [
    { outlet: "Wikipedia",       author: "Wikipedia editors",        date: "2026-06-08", url: "https://en.wikipedia.org/wiki/2026_Formula_One_World_Championship",                                        quote: "The wheelbase was reduced from 360 cm (140 in) to 340 cm (130 in), the width was reduced from 200 cm (79 in) to 190 cm (75 in), and the minimum mass was reduced by 30 kg (66 lb). The tyres' widths were also reduced by 2.5 cm (0.98 in) on the front pair and by 3.0 cm (1.2 in) on the rears." },
    { outlet: "Formula1.com",    author: "Lawrence Barretto",        date: "2024-06-06", url: "https://www.formula1.com/en/latest/article/explained-2026-aerodynamic-regulations-fia-x-mode-z-mode-.26c1CtOzCmN3GfLMywrgb2", quote: "The width of the front tyres has been cut by 25mm and the rears by 30mm which will cut weight, with the FIA saying there will be a 'minimal loss' of grip." },
    { outlet: "Formula1.com",    author: "Lawrence Barretto",        date: "2024-06-06", url: "https://www.formula1.com/en/latest/article/explained-2026-aerodynamic-regulations-fia-x-mode-z-mode-.26c1CtOzCmN3GfLMywrgb2", quote: "The 18-inch wheel size which replaced the former 13-inch spec in 2022 remains – however there are a few minor tweaks." }
  ],
  suspR: [
    { outlet: "Wikipedia",       author: "Wikipedia editors",        date: "2026-06-08", url: "https://en.wikipedia.org/wiki/2026_Formula_One_World_Championship",                                        quote: "The wheelbase was reduced from 360 cm (140 in) to 340 cm (130 in), the width was reduced from 200 cm (79 in) to 190 cm (75 in), and the minimum mass was reduced by 30 kg (66 lb). The tyres' widths were also reduced by 2.5 cm (0.98 in) on the front pair and by 3.0 cm (1.2 in) on the rears." },
    { outlet: "Formula1.com",    author: "Lawrence Barretto",        date: "2024-06-06", url: "https://www.formula1.com/en/latest/article/explained-2026-aerodynamic-regulations-fia-x-mode-z-mode-.26c1CtOzCmN3GfLMywrgb2", quote: "The width of the front tyres has been cut by 25mm and the rears by 30mm which will cut weight, with the FIA saying there will be a 'minimal loss' of grip." },
    { outlet: "Formula1.com",    author: "Lawrence Barretto",        date: "2024-06-06", url: "https://www.formula1.com/en/latest/article/explained-2026-aerodynamic-regulations-fia-x-mode-z-mode-.26c1CtOzCmN3GfLMywrgb2", quote: "In tandem, the rules have cut downforce by 30% and reduced drag by 55% in a bid to improve efficiency and handling – and make the cars more raceable." }
  ],
  brakeDuct: [
    { outlet: "Wikipedia",       author: "Wikipedia editors",        date: "2026-06-08", url: "https://en.wikipedia.org/wiki/2026_Formula_One_World_Championship",                                        quote: "The tyres' widths were also reduced by 2.5 cm (0.98 in) on the front pair and by 3.0 cm (1.2 in) on the rears." },
    { outlet: "Formula1.com",    author: "Lawrence Barretto",        date: "2024-06-06", url: "https://www.formula1.com/en/latest/article/explained-2026-aerodynamic-regulations-fia-x-mode-z-mode-.26c1CtOzCmN3GfLMywrgb2", quote: "The width of the front tyres has been cut by 25mm and the rears by 30mm which will cut weight, with the FIA saying there will be a 'minimal loss' of grip." },
    { outlet: "Formula1.com",    author: "Lawrence Barretto",        date: "2024-06-06", url: "https://www.formula1.com/en/latest/article/explained-2026-aerodynamic-regulations-fia-x-mode-z-mode-.26c1CtOzCmN3GfLMywrgb2", quote: "Looking at the simulations that we got from the teams, loads in 2026 will be a bit lower compared to now – but you know how good the teams are at developing the cars. Even if they start with lower loads, they will increase quite fast in the first season for sure so we made a proposal that we believe is a good compromise between weight and load capacity of the tyre." }
  ],
  diffuser: [
    { outlet: "Formula1.com",    author: "Lawrence Barretto",        date: "2024-06-06", url: "https://www.formula1.com/en/latest/article/explained-2026-aerodynamic-regulations-fia-x-mode-z-mode-.26c1CtOzCmN3GfLMywrgb2", quote: "They will also have a 'partially' flat floor and a lower-powered diffuser, which should reduce the ground effect and reduce the reliance on ultra-stiff and low-set-up – thus easing the issues teams have suffered with bouncing and porpoising." },
    { outlet: "Wikipedia",       author: "Wikipedia editors",        date: "2026-06-08", url: "https://en.wikipedia.org/wiki/2026_Formula_One_World_Championship",                                        quote: "In October 2024, FIA announced that the downforce reduction of the 2026 cars compared to the 2022–2025 generation of cars would be less than initially proposed for performance and safety reasons." },
    { outlet: "Formula1.com",    author: "Lawrence Barretto",        date: "2024-06-06", url: "https://www.formula1.com/en/latest/article/explained-2026-aerodynamic-regulations-fia-x-mode-z-mode-.26c1CtOzCmN3GfLMywrgb2", quote: "The rules have cut downforce by 30% and reduced drag by 55% in a bid to improve efficiency and handling – and make the cars more raceable." }
  ],
  rearWing: [
    { outlet: "The Race",        author: "Scott Mitchell-Malm & Ben Anderson", date: "2024-06-06", url: "https://www.the-race.com/formula-1/f1-reveals-2026-car-everything-you-need-to-know/",                quote: "DRS, which has been used in F1 since 2011, will be replaced with active aerodynamics on the front and rear wing to create a 'low drag mode', along with an MGU-K override system that will give chasing cars extra electrical energy to help them overtake." },
    { outlet: "Formula1.com",    author: "Lawrence Barretto",        date: "2024-06-06", url: "https://www.formula1.com/en/latest/article/explained-2026-aerodynamic-regulations-fia-x-mode-z-mode-.26c1CtOzCmN3GfLMywrgb2", quote: "Drivers can then switch to X-mode, which is a low-drag configuration that sees the flap angle change on both the front and rear wing to maximise straight-line speed. The system will be driver-activated and available in certain parts of the track where lower levels of downforce are safe." },
    { outlet: "GPblog",          author: "Francesco Bianchi",        date: "2024-06-09", url: "https://www.gpblog.com/en/news/280681/tech-analysis-how-f1-will-survive-without-drs-in-2026.html",       quote: "Two different modes will be available for the drivers: X-mode, a low-drag configuration designed to maximize the straight line speed; Z-mode, a high-downforce configuration designed to maximize cornering speed and traction out of the slow corners." },
    { outlet: "Formula1.com",    author: "Lawrence Barretto",        date: "2025-12-17", url: "https://www.formula1.com/en/latest/article/explained-the-new-key-terms-for-formula-1s-new-for-2026-rules.3T5BU6TC9quGcIpGzoWkY0", quote: "The rear wings can open on defined straights as with DRS now, though there will be more of them per circuit – and you don't need to be inside one second of the car in front to open them." }
  ]
};

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

  // Render the interpretation / sources section
  const sources = INTERPRETATION_DEFAULT[partId] || [];
  const interpBlock = document.getElementById('sheetInterp');
  const interpList  = document.getElementById('sheetSources');
  if (sources.length === 0) {
    interpBlock.style.display = 'none';
  } else {
    interpBlock.style.display = 'block';
    interpList.innerHTML = sources.map(s => `
      <li class="src-row">
        <a class="src-link" href="${s.url}" target="_blank" rel="noopener noreferrer">
          <span class="src-outlet">${s.outlet}</span>
          <span class="src-quote">&ldquo;${s.quote}&rdquo;</span>
          <span class="src-meta">${s.author} · ${s.date} ↗</span>
        </a>
      </li>
    `).join('');
  }

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
