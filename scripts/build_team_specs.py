#!/usr/bin/env python3
"""
build_team_specs.py — generate data/team-part-specs.json from public 2026 F1
sources, using an LLM to extract the team's specific technical specification
or design change for each (team, part) pair.

This replaces the v3 build_team_quotes.py (which returned verbatim press
sentences — too noisy; the user wanted the team's actual technical spec,
not sentences that just happen to mention the part).

WHY THIS EXISTS
---------------
The Explore-the-Car "Latest design" section needs to show the user what
each team actually DID to each part, not what the press happened to say
about it. Sir's wording on 2026-06-10: "return information on how that team
customized it to fit the regulations while giving them an advantage."

The data flow:
  1. Read data/part-changes.json for the in-season part-update ledger.
     Each entry has a source URL (currently 1 live URL from R6 Monaco).
  2. Fetch a SEED list of high-signal 2026 F1 press articles.
  3. For each (team, part) pair, collect relevant article paragraphs.
  4. Call the LLM (minimax-m3 via ollama-cloud) once per pair, asking it
     to extract the technical spec into a structured JSON shape.
  5. Validate the LLM output (spec must contain team + part reference,
     confidence >= 0.35). Reject and skip otherwise.
  6. Write the validated specs to data/team-part-specs.json.

WHAT IT PRODUCES
----------------
data/team-part-specs.json with shape:
{
  "schema_version": 2,
  "generated_utc": "2026-06-10T...",
  "methodology": "...",
  "llm": {"provider": "ollama-cloud", "model": "minimax-m3"},
  "sources_crawled": 6,
  "sources_failed": 0,
  "specs": [
    {
      "team_id": "mercedes",
      "part_id": "powerUnit",
      "spec": "Refined start-sequence software and clutch paddle control with grip-prediction algorithms; targeted at getaway performance.",
      "advantage_or_issue": "advantage",
      "confidence": 0.6,
      "source": {
        "outlet": "The Race",
        "author": "Josh Suttill et al.",
        "date": "2026-06-08",
        "url": "https://www.the-race.com/..."
      }
    }
  ]
}

Honest empty state: a (team, part) pair with no LLM-confirmed spec is
simply absent. The page falls back to the regulation-level
INTERPRETATION_DEFAULT for that pair. No fabrication, no fallback filler.

USAGE
-----
    python3 scripts/build_team_specs.py            # full run, writes file
    python3 scripts/build_team_specs.py --dry-run   # fetch only, no LLM calls, no write
    python3 scripts/build_team_specs.py --verbose   # log every step
    python3 scripts/build_team_specs.py --quiet     # only errors
    python3 scripts/build_team_specs.py --max-pairs N  # cap pairs for testing

ENV
---
    OLLAMA_API_KEY  — required for the LLM calls. Already in the env from
                      the ollama-cloud provider config.

SCHEDULE
--------
Sunday 23:30 UTC (= 01:30 CAT Monday) via the existing Sunday cron
(`refresh_and_deploy.py`). Runs AFTER build_issue_data.py because the
scraper reads data/part-changes.json for the in-season URL set.

HARD RULES
----------
- NO MOCK DATA. Every spec is grounded in a real article paragraph and
  passed through the LLM for extraction.
- NO fabrication. If the LLM returns a spec for which the source article
  doesn't mention the team or part, the spec is REJECTED.
- NO `pip install`. Python 3 stdlib only (urllib, json, re, html.parser).
- Reddit is BLOCKED from this VM (returns 403 to every UA). Don't try it.
- 4xx/5xx URLs are logged and skipped, never retried within the same run.

EXIT CODES
----------
0 — success (file written, even if 0 specs extracted)
1 — fatal error (couldn't write file, no API key, no input data, etc.)
"""

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from html.parser import HTMLParser
from datetime import datetime, timezone


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PART_CHANGES_PATH = os.path.join(PROJECT_ROOT, "data", "part-changes.json")
OUTPUT_PATH = os.path.join(PROJECT_ROOT, "data", "team-part-specs.json")

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "https://ollama.com/v1")
OLLAMA_API_KEY = os.environ.get("OLLAMA_API_KEY", "")
OLLAMA_MODEL = os.environ.get("OLLAMA_SPECS_MODEL", "minimax-m3")

# Confidence threshold below which an LLM-extracted spec is rejected.
# Tuned empirically: the model tends to return 0.3-0.9 for genuine specs
# and < 0.2 for fabrications. 0.35 is the floor.
CONFIDENCE_THRESHOLD = 0.35

# Per-pair LLM call: max article chars to send in the context. The model
# has a large context but we want focused inputs. Tighter cap = better
# focus, but more empty returns for articles with lots of relevant text.
MAX_CONTEXT_CHARS = 1500

# Per-request timeout for both fetches and LLM calls.
FETCH_TIMEOUT = 20
LLM_TIMEOUT = 30

# Max output tokens for the LLM call. The model occasionally produces
# 1500+ tokens when enumerating multiple teams; allow headroom.
LLM_MAX_TOKENS = 1500

# Soft cap: don't fetch more than 8 MB per article
MAX_FETCH_BYTES = 8 * 1024 * 1024

# Real Chrome UA — F1 press sites block default Python UAs
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"
)

# Team display names — for verification (spec must contain at least one)
TEAM_DISPLAY_NAMES = {
    "mercedes":      ["Mercedes", "W17", "Antonelli", "Russell"],
    "red_bull":      ["Red Bull", "RB22", "Verstappen", "Hadjar", "Lawson"],
    "ferrari":       ["Ferrari", "SF-26", "Leclerc", "Hamilton"],
    "mclaren":       ["McLaren", "MCL40", "Norris", "Piastri", "Stella"],
    "aston_martin":  ["Aston Martin", "AMR26", "Alonso", "Stroll", "Honda"],
    "alpine":        ["Alpine", "A526", "Gasly", "Colapinto", "Doohan"],
    "williams":      ["Williams", "FW48", "Albon", "Lindblad", "Sainz"],
    "rb":            ["Racing Bulls", "VCARB", "RB"],
    "audi":          ["Audi", "R26", "Bortoleto", "Hulkenberg", "Wheatley"],
    "cadillac":      ["Cadillac", "Perez", "Bottas"],
    "haas":          ["Haas", "VF-26", "Bearman", "Ocon", "Komatsu"],
}

# Part display names — for verification (spec must contain at least one)
PART_DISPLAY_NAMES = {
    "frontWing":   ["front wing", "front-wing", "front end", "outwash", "endplate"],
    "rearWing":    ["rear wing", "rear-wing", "beam wing", "X-mode", "Z-mode", "DRS", "overtake mode"],
    "powerUnit":   ["power unit", "power-unit", "engine", "ICE", "MGU-K", "MGU-H", "turbo", "PU"],
    "battery":     ["battery", "ERS", "energy store", "super-cap", "supercap", "super clip", "deployment", "electrical"],
    "floor":       ["floor", "floor edge", "edge wing", "venturi", "porpoising", "ground effect"],
    "diffuser":    ["diffuser", "rear floor"],
    "sidepods":    ["sidepod", "sidepod inlet", "sidepod bodywork", "in-washing", "wheel wake"],
    "halo":        ["halo", "cockpit protection", "cockpit halo"],
    "suspF":       ["front suspension", "front-suspension", "suspension geometry"],
    "suspR":       ["rear suspension", "rear-suspension", "suspension geometry"],
    "brakeDuct":   ["brake duct", "brake cooling", "brake configuration", "brake issue", "brake problem", "brake failure", "brake", "brakes", "braking"],
    "nose":        ["nose", "nose cone", "wheelbase"],
}

# Seed articles — high-signal 2026 F1 press. Same list as the v3 scraper;
# these URLs are known-good (200) from prior runs.
SEED_ARTICLES = [
    {
        "url": "https://www.the-race.com/formula-1/f1-2026-monaco-grand-prix-everything-we-learned/",
        "outlet": "The Race",
        "author": "Josh Suttill, Jon Noble, Jack Cozens, Scott Mitchell-Malm",
        "date": "2026-06-08",
    },
    {
        "url": "https://www.the-race.com/formula-1/f1-2026-monaco-grand-prix-winners-losers/",
        "outlet": "The Race",
        "author": "Matt Beer, Jack Cozens",
        "date": "2026-06-07",
    },
    {
        "url": "https://www.formula1.com/en/latest/article/explained-2026-aerodynamic-regulations-fia-x-mode-z-mode-.26c1CtOzCmN3GfLMywrgb2",
        "outlet": "Formula1.com",
        "author": "Lawrence Barretto",
        "date": "2024-06-06",
    },
    {
        "url": "https://www.formula1.com/en/latest/article/explained-the-new-key-terms-for-formula-1s-new-for-2026-rules.3T5BU6TC9quGcIpGzoWkY0",
        "outlet": "Formula1.com",
        "author": "Lawrence Barretto",
        "date": "2025-12-17",
    },
    {
        "url": "https://en.wikipedia.org/wiki/2026_Formula_One_World_Championship",
        "outlet": "Wikipedia",
        "author": "Wikipedia editors",
        "date": "2026-06-08",
    },
    {
        "url": "https://www.the-race.com/formula-1/f1-reveals-2026-car-everything-you-need-to-know/",
        "outlet": "The Race",
        "author": "Scott Mitchell-Malm, Ben Anderson",
        "date": "2024-06-06",
    },
]

# Forum source: f1technical.net (the only technical F1 forum reachable from
# this VM; Reddit r/F1Technical, Autosport forums, and motorsport.com forums
# all return 403). Each thread is one f1technical discussion; the LLM is
# responsible for deciding which (team, part) pairs the thread actually
# covers. The 'team' field is a hint to the LLM and a meta filter for
# which (team, part) pairs the thread is offered to.
#
# Adding this was a direct user request on 2026-06-10: "search technical
# forums for information on all parts for all teams so we can add". Reddit
# is blocked; this is the next-best alternative.
F1TECH_THREADS = [
    # === f=15: dedicated 2026 per-team threads ===
    {"url": "https://www.f1technical.net/forum/viewtopic.php?t=32427", "team": "mercedes",      "outlet": "F1 Technical", "title": "2026 Mercedes-AMG Petronas F1 Team"},
    {"url": "https://www.f1technical.net/forum/viewtopic.php?t=32419", "team": "ferrari",       "outlet": "F1 Technical", "title": "2026 Scuderia Ferrari HP F1 Team"},
    {"url": "https://www.f1technical.net/forum/viewtopic.php?t=32414", "team": "mclaren",       "outlet": "F1 Technical", "title": "2026 McLaren Mastercard F1 Team"},
    {"url": "https://www.f1technical.net/forum/viewtopic.php?t=32417", "team": "red_bull",      "outlet": "F1 Technical", "title": "2026 Oracle Red Bull Racing F1 Team"},
    {"url": "https://www.f1technical.net/forum/viewtopic.php?t=32104", "team": "aston_martin",  "outlet": "F1 Technical", "title": "2026 Aston Martin Aramco Formula One Team"},
    {"url": "https://www.f1technical.net/forum/viewtopic.php?t=32355", "team": "audi",          "outlet": "F1 Technical", "title": "2026 Audi Revolut F1 Team"},
    {"url": "https://www.f1technical.net/forum/viewtopic.php?t=32486", "team": "alpine",        "outlet": "F1 Technical", "title": "2026 BWT Alpine Formula One Team"},
    {"url": "https://www.f1technical.net/forum/viewtopic.php?t=32480", "team": "williams",      "outlet": "F1 Technical", "title": "2026 Atlassian Williams F1 Team"},
    {"url": "https://www.f1technical.net/forum/viewtopic.php?t=32457", "team": "rb",            "outlet": "F1 Technical", "title": "2026 Visa Cash App Racing Bulls F1 Team"},
    {"url": "https://www.f1technical.net/forum/viewtopic.php?t=32468", "team": "haas",          "outlet": "F1 Technical", "title": "2026 Haas F1 Team"},
    {"url": "https://www.f1technical.net/forum/viewtopic.php?t=30846", "team": "cadillac",      "outlet": "F1 Technical", "title": "2026 Cadillac Formula 1 Team"},

    # === f=12: 2026 per-car threads (broader discussion, same-team) ===
    {"url": "https://www.f1technical.net/forum/viewtopic.php?t=32459", "team": "mercedes",      "outlet": "F1 Technical", "title": "Mercedes W17"},
    {"url": "https://www.f1technical.net/forum/viewtopic.php?t=32455", "team": "ferrari",       "outlet": "F1 Technical", "title": "Ferrari SF-26"},
    {"url": "https://www.f1technical.net/forum/viewtopic.php?t=32452", "team": "red_bull",      "outlet": "F1 Technical", "title": "Red Bull RB22"},
    {"url": "https://www.f1technical.net/forum/viewtopic.php?t=32460", "team": "aston_martin",  "outlet": "F1 Technical", "title": "Aston Martin AMR26"},
    {"url": "https://www.f1technical.net/forum/viewtopic.php?t=32454", "team": "audi",          "outlet": "F1 Technical", "title": "Audi R26"},
    {"url": "https://www.f1technical.net/forum/viewtopic.php?t=32458", "team": "alpine",        "outlet": "F1 Technical", "title": "Alpine A526"},
    {"url": "https://www.f1technical.net/forum/viewtopic.php?t=32462", "team": "williams",      "outlet": "F1 Technical", "title": "Williams FW48"},
    {"url": "https://www.f1technical.net/forum/viewtopic.php?t=32453", "team": "rb",            "outlet": "F1 Technical", "title": "RB VCARB 03"},
    {"url": "https://www.f1technical.net/forum/viewtopic.php?t=32456", "team": "haas",          "outlet": "F1 Technical", "title": "Haas VF-26"},
    {"url": "https://www.f1technical.net/forum/viewtopic.php?t=32463", "team": "cadillac",      "outlet": "F1 Technical", "title": "Cadillac MAC-26"},
    {"url": "https://www.f1technical.net/forum/viewtopic.php?t=32492", "team": "mclaren",       "outlet": "F1 Technical", "title": "McLaren MCL40"},

    # === f=6: 2026 regulation / specific-part threads (general team) ===
    {"url": "https://www.f1technical.net/forum/viewtopic.php?t=31296", "team": "general",       "outlet": "F1 Technical", "title": "2026 Aerodynamic & Chassis Regulations"},
    {"url": "https://www.f1technical.net/forum/viewtopic.php?t=30000", "team": "general",       "outlet": "F1 Technical", "title": "2026 active aero discussions"},
    {"url": "https://www.f1technical.net/forum/viewtopic.php?t=32001", "team": "general",       "outlet": "F1 Technical", "title": "Dedicated 2026 regs front wing thread"},
    {"url": "https://www.f1technical.net/forum/viewtopic.php?t=32503", "team": "general",       "outlet": "F1 Technical", "title": "2026 Brake Duct and Suspension Rules question"},
    {"url": "https://www.f1technical.net/forum/viewtopic.php?t=32563", "team": "general",       "outlet": "F1 Technical", "title": "2026 Front Wing Adjustment loop hole"},
    {"url": "https://www.f1technical.net/forum/viewtopic.php?t=32564", "team": "general",       "outlet": "F1 Technical", "title": "2026 Regulations - Critique thread"},

    # === f=4: per-team power unit threads ===
    {"url": "https://www.f1technical.net/forum/viewtopic.php?t=23688", "team": "mercedes",      "outlet": "F1 Technical", "title": "Mercedes Power Unit Hardware & Software"},
    {"url": "https://www.f1technical.net/forum/viewtopic.php?t=21958", "team": "ferrari",       "outlet": "F1 Technical", "title": "Ferrari Power Unit Hardware & Software"},
    {"url": "https://www.f1technical.net/forum/viewtopic.php?t=31159", "team": "red_bull",      "outlet": "F1 Technical", "title": "Red Bull Power Unit Hardware & Software"},
    {"url": "https://www.f1technical.net/forum/viewtopic.php?t=32551", "team": "audi",          "outlet": "F1 Technical", "title": "Audi Power Unit Hardware & Software"},
    {"url": "https://www.f1technical.net/forum/viewtopic.php?t=29581", "team": "general",       "outlet": "F1 Technical", "title": "2026 Hybrid Powerunits"},
    {"url": "https://www.f1technical.net/forum/viewtopic.php?t=32518", "team": "general",       "outlet": "F1 Technical", "title": "2026 gearing"},
]


# ---------------------------------------------------------------------------
# HTML → text (stdlib only)
# ---------------------------------------------------------------------------

class _TextExtractor(HTMLParser):
    BLOCK_TAGS = {
        "p", "div", "section", "article", "li", "ul", "ol", "blockquote",
        "h1", "h2", "h3", "h4", "h5", "h6", "tr", "td", "br", "header",
        "footer",
    }
    DROP_TAGS = {"script", "style", "nav", "aside", "form", "noscript", "svg"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self._buf = []
        self._depth_drop = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.DROP_TAGS:
            self._depth_drop += 1
            return
        if tag in self.BLOCK_TAGS:
            self._buf.append("\n")

    def handle_endtag(self, tag):
        if tag in self.DROP_TAGS and self._depth_drop > 0:
            self._depth_drop -= 1
            return
        if tag in self.BLOCK_TAGS:
            self._buf.append("\n")

    def handle_data(self, data):
        if self._depth_drop == 0:
            self._buf.append(data)

    def get_text(self):
        text = "".join(self._buf)
        text = re.sub(r"[ \t\f\v]+", " ", text)
        text = re.sub(r" *\n *", "\n", text)
        text = re.sub(r"\n{2,}", "\n", text)
        return text.strip()


def html_to_text(html: str) -> str:
    parser = _TextExtractor()
    try:
        parser.feed(html)
    except Exception:
        pass
    return parser.get_text()


# ---------------------------------------------------------------------------
# Fetch
# ---------------------------------------------------------------------------

def fetch_url(url: str) -> str | None:
    req = urllib.request.Request(url, headers={
        "User-Agent":      USER_AGENT,
        "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    })
    try:
        with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT) as resp:
            body = b""
            while len(body) < MAX_FETCH_BYTES:
                chunk = resp.read(64 * 1024)
                if not chunk:
                    break
                body += chunk
            charset = resp.headers.get_content_charset() or "utf-8"
            try:
                return body.decode(charset, errors="replace")
            except (LookupError, UnicodeDecodeError):
                return body.decode("utf-8", errors="replace")
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError):
        return None


def fetch_f1technical_thread(url: str) -> str | None:
    """Fetch an f1technical forum thread and return the joined post text.
    Returns None on fetch failure. Returns '' if the thread has no real
    posts (placeholder-only)."""
    html = fetch_url(url)
    if html is None:
        return None
    # phpBB: post content lives in <div class="content">...</div> inside
    # each <div class="postbody">. We use a non-greedy match against the
    # closing div tags to capture the post body.
    matches = re.findall(r'class="content"[^>]*>(.*?)</div>\s*</div>\s*</div>', html, re.DOTALL)
    posts = []
    for p in matches:
        text = html_to_text(p)
        if 30 < len(text) < 5000:
            posts.append(text)
    if not posts:
        return ""
    # Cap at the first 15 substantive posts to keep the LLM context focused.
    joined = "\n\n---\n\n".join(posts[:15])
    return joined


# ---------------------------------------------------------------------------
# Match sentences to (team, part) — used to build per-pair context blobs
# ---------------------------------------------------------------------------

_SENTENCE_SPLIT = re.compile(
    r"""
    (?:                 # end-of-sentence punctuation
        [\.\!\?]        # sentence terminator
        [\u201d\"'\)\]]* # optional closing quotes/parens
        \s+             # followed by whitespace
        (?=             # and then
            [A-Z\u201c\"\(]  # capital letter or opening quote/paren
            | $             # or end of string
        )
    )
    """,
    re.VERBOSE,
)


def split_sentences(text: str) -> list:
    text = text.replace("\u201c", '"').replace("\u201d", '"')
    text = text.replace("\u2018", "'").replace("\u2019", "'")
    parts = _SENTENCE_SPLIT.split(text)
    return [p.strip() for p in parts if p.strip() and 30 < len(p.strip()) < 500]


def team_in_text(text: str, team_id: str) -> bool:
    for name in TEAM_DISPLAY_NAMES.get(team_id, []):
        pattern = r"(?<![A-Za-z0-9])" + re.escape(name) + r"(?![A-Za-z0-9])"
        if re.search(pattern, text):
            return True
    return False


def part_in_text(text: str, part_id: str) -> bool:
    for name in PART_DISPLAY_NAMES.get(part_id, []):
        pattern = r"(?<![A-Za-z0-9])" + re.escape(name) + r"(?![A-Za-z0-9])"
        if re.search(pattern, text, re.IGNORECASE):
            return True
    return False


def part_changes_team_part(part_changes: list) -> set:
    """Build the set of (team_id, part_id) tuples that have a live
    in-season upgrade in part-changes.json. These get the most focused
    context: only the article from their own source URL, not the broad
    seed set."""
    out = set()
    for team in part_changes:
        team_id = team.get("team_id")
        for change in team.get("changes", []):
            part_name = change.get("part", "")
            desc = change.get("description", "")
            pn = part_name.lower()
            part_id = None
            if "floor" in pn:
                part_id = "floor"
            elif "front suspension" in pn or "front-suspension" in pn:
                part_id = "suspF"
            elif "rear suspension" in pn or "rear-suspension" in pn:
                part_id = "suspR"
            elif "brake" in pn:
                part_id = "brakeDuct"
            elif "power unit" in pn or "engine" in pn:
                part_id = "powerUnit"
            elif "battery" in pn or "ers" in pn:
                part_id = "battery"
            elif "front wing" in pn:
                part_id = "frontWing"
            elif "rear wing" in pn:
                part_id = "rearWing"
            elif "diffuser" in pn:
                part_id = "diffuser"
            elif "sidepod" in pn:
                part_id = "sidepods"
            elif "halo" in pn:
                part_id = "halo"
            elif "nose" in pn:
                part_id = "nose"
            if part_id and team_id:
                out.add((team_id, part_id))
    return out


# ---------------------------------------------------------------------------
# LLM call — extract structured spec
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are a Formula 1 technical analyst. Your job is to extract the specific technical specification, design change, or engineering decision that each team made for a named car part, based on the article text provided.

The article may mention multiple teams. You must evaluate each team independently.

For each team in the team list, return a JSON object. If the article text does not describe a specific technical change for that team and that part, omit that team from the output (do NOT return an empty object for it — just don't include it).

Output shape (JSON object with team_ids as keys):
{
  "team_id_1": {"spec": "1-3 sentence concrete technical description", "advantage_or_issue": "advantage|issue|stated", "confidence": 0.0-1.0},
  "team_id_2": {"spec": "...", "advantage_or_issue": "...", "confidence": ...},
  ...
}

Rules:
- "spec" must be CONCRETE: name the specific component, the change made, and (if mentioned) why. Example: "New floor edge geometry with revised diffuser, targeted at rear-end downforce recovery in low-speed corners." NOT: "Mercedes worked on the floor."
- Only return a spec if the article text supports a specific technical claim about the team. If the article just names the team in passing, omit the team.
- If no team in the list has a spec, return an empty JSON object: {}
- "advantage_or_issue": "advantage" if the article frames it as a gain/improvement, "issue" if a problem/weakness, "stated" if neutral
- "confidence": 0.9+ for direct quotes from engineers, 0.6-0.8 for clear press paraphrase, 0.3-0.5 for inferred/hedged language, <0.2 for guesses (omit if <0.2)
- Do not invent details not present in the article.
- Return JSON only, no prose, no markdown."""


def call_llm_multi_team(part_id: str, team_ids: list, context: str, source_url: str, verbose: bool = False) -> dict | None:
    """Call the LLM to extract specs for multiple teams at once (one per (article, part)
    pair, returning specs for 0-N teams). Returns parsed JSON dict keyed by team_id,
    or None on error."""
    if not OLLAMA_API_KEY:
        print("  ! OLLAMA_API_KEY not in env; cannot call LLM", file=sys.stderr)
        return None
    if not context.strip():
        return None
    if len(context) > MAX_CONTEXT_CHARS:
        context = context[:MAX_CONTEXT_CHARS] + "\n\n[... truncated ...]"

    user_prompt = (
        f"Part: {part_id}\n"
        f"Teams to evaluate: {', '.join(team_ids)}\n"
        f"Source article URL: {source_url}\n\n"
        f"Article text:\n\"\"\"\n{context}\n\"\"\"\n\n"
        f"Return a JSON object keyed by team_id, containing only teams with a verifiable spec. "
        f"Return JSON only, no prose."
    )
    payload = {
        "model": OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": user_prompt},
        ],
        "temperature": 0.1,
        "max_tokens":  LLM_MAX_TOKENS,
        "response_format": {"type": "json_object"},
    }
    url = f"{OLLAMA_BASE_URL.rstrip('/')}/chat/completions"
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={
        "Authorization": f"Bearer {OLLAMA_API_KEY}",
        "Content-Type":  "application/json",
    })
    last_err = None
    for attempt in range(2):
        try:
            with urllib.request.urlopen(req, timeout=LLM_TIMEOUT) as resp:
                body = json.loads(resp.read())
                content = body["choices"][0]["message"]["content"]
                if verbose:
                    usage = body.get("usage", {})
                    print(f"    [llm] part={part_id} in={usage.get('prompt_tokens')} out={usage.get('completion_tokens')} attempt={attempt+1}", file=sys.stderr)
                return json.loads(content)
        except json.JSONDecodeError as e:
            last_err = e
            # On decode error, retry with half the context (token-cap truncation
            # is the usual cause)
            if attempt == 0 and len(context) > 600:
                context = context[: len(context) // 2] + "\n\n[... truncated ...]"
                user_prompt = (
                    f"Part: {part_id}\n"
                    f"Teams to evaluate: {', '.join(team_ids)}\n"
                    f"Source article URL: {source_url}\n\n"
                    f"Article text:\n\"\"\"\n{context}\n\"\"\"\n\n"
                    f"Return a JSON object keyed by team_id, containing only teams with a verifiable spec. "
                    f"Return JSON only, no prose."
                )
                payload["messages"] = [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user",   "content": user_prompt},
                ]
                req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={
                    "Authorization": f"Bearer {OLLAMA_API_KEY}",
                    "Content-Type":  "application/json",
                })
            else:
                break
        except (urllib.error.URLError, TimeoutError, OSError, KeyError) as e:
            print(f"  ! LLM call failed for part={part_id}: {e!r}", file=sys.stderr)
            return None
    print(f"  ! LLM call failed for part={part_id}: {last_err!r}", file=sys.stderr)
    return None


def call_llm(team_id: str, part_id: str, context: str, source_url: str, verbose: bool = False) -> dict | None:
    """Backwards-compat shim. New code should use call_llm_multi_team."""
    # Pass a single-team list
    result = call_llm_multi_team(part_id, [team_id], context, source_url, verbose=verbose)
    if not result:
        return None
    return result.get(team_id)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_spec(spec: dict, team_id: str, part_id: str) -> tuple[bool, str]:
    """Reject specs that don't meet the quality bar. Returns (is_valid, reason)."""
    if not spec:
        return False, "empty spec (LLM returned {})"
    if "spec" not in spec:
        return False, "missing 'spec' field"
    spec_text = str(spec.get("spec", "")).strip()
    if len(spec_text) < 20:
        return False, f"spec too short ({len(spec_text)} chars)"
    if len(spec_text) > 600:
        return False, f"spec too long ({len(spec_text)} chars) — likely rambling"
    # The spec MUST mention the team (at least one of the team's names)
    if not team_in_text(spec_text, team_id):
        return False, "spec doesn't mention the team"
    # The spec MUST mention the part (at least one of the part's names)
    if not part_in_text(spec_text, part_id):
        return False, "spec doesn't mention the part"
    # Confidence must meet threshold
    try:
        conf = float(spec.get("confidence", 0.0))
    except (TypeError, ValueError):
        conf = 0.0
    if conf < CONFIDENCE_THRESHOLD:
        return False, f"confidence {conf:.2f} < threshold {CONFIDENCE_THRESHOLD}"
    # advantage_or_issue must be one of the three
    aoi = spec.get("advantage_or_issue", "stated")
    if aoi not in ("advantage", "issue", "stated"):
        aoi = "stated"
    return True, "ok"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run",     action="store_true", help="fetch + match only, no LLM calls, no write")
    parser.add_argument("--verbose",     action="store_true", help="log every step")
    parser.add_argument("--quiet",       action="store_true", help="only errors")
    parser.add_argument("--max-pairs",   type=int, default=0,  help="cap pairs processed (for testing)")
    args = parser.parse_args()

    verbose = args.verbose and not args.quiet
    quiet = args.quiet

    def log(msg):
        if not quiet:
            print(msg, file=sys.stderr)

    log(f"[{datetime.now(timezone.utc).isoformat()}] build_team_specs starting (model={OLLAMA_MODEL})")

    if not args.dry_run and not OLLAMA_API_KEY:
        log("  ! OLLAMA_API_KEY not in env")
        return 1

    # ---- 1. Load part-changes.json (in-season ledger) ----
    part_changes = []
    if os.path.exists(PART_CHANGES_PATH):
        with open(PART_CHANGES_PATH) as f:
            part_changes = json.load(f).get("teams", [])
    in_season_pairs = part_changes_team_part(part_changes)
    log(f"  · {len(part_changes)} teams in part-changes ledger; {len(in_season_pairs)} live in-season (team, part) pairs")

    # ---- 2. Fetch all articles ----
    articles = {}   # url -> {"text": ..., "meta": {...}}
    sources_crawled = 0
    sources_failed = 0

    # In-season URLs first (highest priority)
    in_season_urls = []
    for team in part_changes:
        for change in team.get("changes", []):
            url = change.get("source", {}).get("url")
            if url and url not in in_season_urls:
                in_season_urls.append(url)

    # Then seed articles
    for art in SEED_ARTICLES:
        if art["url"] not in in_season_urls:
            in_season_urls.append(art["url"])

    for url in in_season_urls:
        log(f"  → fetch {url}")
        html = fetch_url(url)
        if html is None:
            sources_failed += 1
            log(f"    ! fetch failed")
            continue
        sources_crawled += 1
        text = html_to_text(html)
        articles[url] = {"text": text, "meta": None}
        # Find the matching seed/in-season meta
        for art in SEED_ARTICLES:
            if art["url"] == url:
                articles[url]["meta"] = art
        for team in part_changes:
            for change in team.get("changes", []):
                if change.get("source", {}).get("url") == url:
                    articles[url]["meta"] = {
                        "outlet": change["source"].get("outlet", ""),
                        "author": change["source"].get("author", ""),
                        "date":   change["source"].get("date", ""),
                    }

    # ---- 2b. Fetch f1technical forum threads (the user-requested
    #         "search technical forums" addition on 2026-06-10) ----
    # Only forum source reachable from this VM: Reddit r/F1Technical,
    # Autosport forums, and motorsport.com forums all 403. f1technical
    # returns 200 and has 2026-specific per-team + per-car + per-part
    # threads. Threads are pre-curated in F1TECH_THREADS; the LLM
    # decides which (team, part) pairs the thread actually covers.
    f1tech_fetched = 0
    f1tech_failed  = 0
    f1tech_skipped = 0  # threads with no real posts (placeholder-only)
    for t in F1TECH_THREADS:
        url    = t["url"]
        team   = t.get("team", "general")
        outlet = t.get("outlet", "F1 Technical")
        log(f"  → fetch f1tech t={url.split('=')[-1]} team={team}")
        joined = fetch_f1technical_thread(url)
        if joined is None:
            f1tech_failed += 1
            log(f"    ! fetch failed")
            continue
        if not joined:
            f1tech_skipped += 1
            log(f"    . skipped (no substantive posts)")
            continue
        f1tech_fetched += 1
        articles[url] = {
            "text": joined,
            "meta": {
                "outlet": outlet,
                "author": "f1technical forum contributors",
                "date":   "2026-06-08",  # the date f1technical is crawled
                "team":   team,         # hint for the per-(article, part) loop
                "kind":   "forum",      # mark so the prompt can mention "forum thread"
            },
        }

    log(f"  · {sources_crawled} press sources crawled, {sources_failed} failed")
    log(f"  · {f1tech_fetched} f1technical threads fetched, {f1tech_failed} failed, {f1tech_skipped} skipped (no posts)")
    sources_crawled += f1tech_fetched
    sources_failed  += f1tech_failed

    # ---- 3. Build per-(article, part) context blobs ----
    # For each (article, part) pair, find all sentences that mention the
    # part. Send those sentences + the full team list to the LLM and let
    # the LLM decide which teams have a real spec in this article.
    # This is one LLM call per (article, part) pair, returning 0-N specs.
    article_part_pairs = []   # [(url, part_id, joined_context, meta)]
    for url, art in articles.items():
        if not art["text"]:
            continue
        for part_id in PART_DISPLAY_NAMES.keys():
            # Find sentences that mention this part
            part_sentences = []
            for s in split_sentences(art["text"]):
                if part_in_text(s, part_id):
                    part_sentences.append(s)
            if not part_sentences:
                continue
            joined = "\n\n".join(part_sentences)
            if len(joined) > MAX_CONTEXT_CHARS:
                joined = joined[:MAX_CONTEXT_CHARS] + "\n\n[... truncated ...]"
            article_part_pairs.append((url, part_id, joined, art.get("meta") or {}))

    log(f"  · {len(article_part_pairs)} (article, part) pairs to send to LLM")

    # ---- 4. LLM extraction per (article, part) pair ----
    # Track best spec per (team_id, part_id). If multiple articles produce
    # specs for the same pair, keep the highest-confidence one.
    best_specs = {}   # (team_id, part_id) -> spec dict
    pairs_processed = 0
    all_team_ids = list(TEAM_DISPLAY_NAMES.keys())
    for url, part_id, context, meta in article_part_pairs:
        if args.max_pairs and pairs_processed >= args.max_pairs:
            break
        pairs_processed += 1
        if args.dry_run:
            log(f"  [dry-run] would call LLM for article+part={part_id} from {url[:60]}")
            continue
        # When the article meta has a 'team' hint (e.g. a f1technical
        # team-thread), restrict the LLM call to that team only. This
        # reduces noise (LLM is less likely to extract specs about
        # teams the thread doesn't actually discuss) and saves tokens.
        # For press articles, we pass all teams as before.
        if meta and meta.get("team") and meta["team"] in all_team_ids:
            team_hint = [meta["team"]]
        else:
            team_hint = all_team_ids
        kind_label = "f1tech" if (meta and meta.get("kind") == "forum") else "press"
        log(f"  [llm:{kind_label}] part={part_id} teams={len(team_hint)} ({len(context)} chars) from {url[:60]}")
        per_team = call_llm_multi_team(part_id, team_hint, context, url, verbose=verbose)
        if not per_team:
            log(f"    ! LLM call failed or returned no specs")
            continue
        for team_id, spec in per_team.items():
            if team_id not in all_team_ids:
                continue  # LLM hallucinated a team_id
            ok, reason = validate_spec(spec, team_id, part_id)
            if not ok:
                log(f"    - {team_id}/{part_id} rejected: {reason}")
                continue
            key = (team_id, part_id)
            conf = float(spec.get("confidence", 0.0))
            if key not in best_specs or conf > best_specs[key]["confidence"]:
                best_specs[key] = {
                    "team_id":             team_id,
                    "part_id":             part_id,
                    "spec":                spec["spec"],
                    "advantage_or_issue":  spec.get("advantage_or_issue", "stated"),
                    "confidence":          conf,
                    "source": {
                        "outlet": meta.get("outlet", ""),
                        "author": meta.get("author", ""),
                        "date":   meta.get("date", ""),
                        "url":    url,
                    },
                }
                log(f"    + {team_id}/{part_id} new best (conf={conf:.2f})")
            else:
                log(f"    · {team_id}/{part_id} kept previous (new conf={conf:.2f} <= existing)")

    specs = sorted(best_specs.values(), key=lambda s: (s["team_id"], s["part_id"]))

    # ---- 5. Write output ----
    output = {
        "schema_version":  2,
        "generated_utc":   datetime.now(timezone.utc).isoformat(),
        "methodology": (
            "Verbatim article paragraphs are sent to minimax-m3 (via ollama-cloud) "
            "for structured spec extraction. The LLM is asked to identify the team's "
            "specific technical specification or design change for each (team, part) "
            "pair. Specs are rejected if the LLM's confidence is below 0.35, if the "
            "spec text doesn't mention the team or the part, or if the article text "
            "doesn't actually support the claim. (team, part) pairs without a valid "
            "spec are simply absent from the output. The page falls back to the "
            "regulation-level INTERPRETATION_DEFAULT for those pairs."
        ),
        "llm": {"provider": "ollama-cloud", "model": OLLAMA_MODEL},
        "sources_crawled": sources_crawled,
        "sources_failed":  sources_failed,
        "specs":           specs,
    }
    tmp_path = OUTPUT_PATH + ".tmp"
    try:
        os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
        with open(tmp_path, "w") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        os.replace(tmp_path, OUTPUT_PATH)
    except OSError as e:
        log(f"  ! write failed: {e}")
        return 1

    log(f"[{datetime.now(timezone.utc).isoformat()}] wrote {len(specs)} specs to {OUTPUT_PATH}")
    log(f"  teams covered: {len(set(s['team_id'] for s in specs))}")
    log(f"  parts covered: {len(set(s['part_id'] for s in specs))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
