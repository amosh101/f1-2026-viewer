#!/usr/bin/env python3
"""
run_full_scrape.py — One-off full-pipeline scrape using ALL available sources
(press, f1tech, planetf1, gpblog, racefans). Writes data/team-part-specs.json
when done. Manual-mode run, not part of the regular Sunday cron.
"""
import os
import re
import json
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone
from collections import defaultdict

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"
OLLAMA_BASE = "https://ollama.com/v1"
# Read OLLAMA_API_KEY from .env or env var. Hardcoding a key in source is
# a security anti-pattern; the script inherits the env when run from
# the cron / from a properly-configured shell. As a fallback, try
# reading from ~/.bashrc-style files.
import os
def _read_env():
    key = os.environ.get("OLLAMA_API_KEY", "")
    if key: return key
    # Try common env files
    for path in ["/root/.hermes/.env", "/root/.env", os.path.expanduser("~/.ollama-key")]:
        try:
            with open(path) as f:
                for line in f:
                    if line.startswith("OLLAMA_API_KEY="):
                        return line.split("=", 1)[1].strip().strip('"').strip("'")
        except: pass
    return ""
OLLAMA_KEY = _read_env()
OLLAMA_MODEL = "minimax-m3"

# === TEAM / PART DICTIONARIES (same as build_team_specs.py) ===
TEAM_DISPLAY = {
    "mercedes":     ["Mercedes", "W17", "Antonelli", "Russell"],
    "red_bull":     ["Red Bull", "RB22", "Verstappen", "Hadjar", "Lawson"],
    "ferrari":      ["Ferrari", "SF-26", "Leclerc", "Hamilton"],
    "mclaren":      ["McLaren", "MCL40", "Norris", "Piastri", "Stella"],
    "aston_martin": ["Aston Martin", "AMR26", "Alonso", "Stroll", "Honda"],
    "alpine":       ["Alpine", "A526", "Gasly", "Colapinto", "Doohan"],
    "williams":     ["Williams", "FW48", "Albon", "Lindblad", "Sainz"],
    "rb":           ["Racing Bulls", "VCARB", "RB"],
    "audi":         ["Audi", "R26", "Bortoleto", "Hulkenberg", "Wheatley"],
    "cadillac":     ["Cadillac", "Perez", "Bottas"],
    "haas":         ["Haas", "VF-26", "Bearman", "Ocon", "Komatsu"],
}
PART_DISPLAY = {
    "frontWing":   ["front wing", "front-wing", "front end", "outwash", "endplate"],
    "rearWing":    ["rear wing", "rear-wing", "beam wing", "X-mode", "Z-mode", "DRS", "overtake mode", "active aero"],
    "powerUnit":   ["power unit", "power-unit", "engine", "ICE", "MGU-K", "MGU-H", "turbo", "PU", "Brembo", "Carbone Industries"],
    "battery":     ["battery", "ERS", "energy store", "super-cap", "supercap", "super clip", "deployment", "electrical", "hot swap"],
    "floor":       ["floor", "floor edge", "edge wing", "venturi", "porpoising", "ground effect", "diffuser hole"],
    "diffuser":    ["diffuser", "rear floor", "y-zero", "phantom flow"],
    "sidepods":    ["sidepod", "sidepod inlet", "sidepod bodywork", "in-washing", "wheel wake"],
    "halo":        ["halo", "cockpit protection", "cockpit halo"],
    "suspF":       ["front suspension", "front-suspension", "suspension geometry", "pull-rod", "push-rod"],
    "suspR":       ["rear suspension", "rear-suspension", "suspension geometry", "pull-rod"],
    "brakeDuct":   ["brake duct", "brake cooling", "brake configuration", "brake material", "brake feel", "brake disc", "brake pad", "brake", "brakes", "braking"],
    "nose":        ["nose", "nose cone", "wheelbase", "short vertical", "nose-to-front"],
}
ALL_TEAMS = list(TEAM_DISPLAY.keys())
ALL_PARTS = list(PART_DISPLAY.keys())

# === SENTENCE SPLIT + HELPERS ===
_SENT_RE = re.compile(r'(?:[\.\!\?][\u201d\"\)\]]*\s+(?=[A-Z\u201c\"\(]|$))')
def split_sentences(text):
    text = text.replace('\u201c', '"').replace('\u201d', '"').replace('\u2018', "'").replace('\u2019', "'")
    parts = _SENT_RE.split(text)
    return [p.strip() for p in parts if p.strip() and 30 < len(p.strip()) < 600]

def team_in_text(text, team_id):
    for name in TEAM_DISPLAY.get(team_id, []):
        pattern = r'(?<![A-Za-z0-9])' + re.escape(name) + r'(?![A-Za-z0-9])'
        if re.search(pattern, text, re.IGNORECASE):
            return True
    return False

def part_in_text(text, part_id):
    for name in PART_DISPLAY.get(part_id, []):
        pattern = r'(?<![A-Za-z0-9])' + re.escape(name) + r'(?![A-Za-z0-9])'
        if re.search(pattern, text, re.IGNORECASE):
            return True
    return False

# === FETCH ===
def fetch(url, timeout=12):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode('utf-8', errors='replace')
    except: return None

def html_to_text(html):
    html = re.sub(r'<script[^>]*>.*?</script>', ' ', html, flags=re.DOTALL)
    html = re.sub(r'<style[^>]*>.*?</style>', ' ', html, flags=re.DOTALL)
    html = re.sub(r'<br\s*/?>', '\n', html)
    html = re.sub(r'<[^>]+>', ' ', html)
    html = re.sub(r'\s+', ' ', html)
    return html.strip()

# === LLM ===
SYSTEM_PROMPT = """You are a Formula 1 technical analyst. Your job is to extract the specific technical specification, design change, or engineering decision that each team made for a named car part, based on the article text provided.

The article may mention multiple teams. You must evaluate each team independently.

For each team in the team list, return a JSON object. If the article text does not describe a specific technical change for that team and that part, omit that team from the output (do NOT return an empty object for it).

Output shape (JSON object with team_ids as keys):
{
  "team_id_1": {"spec": "1-3 sentence concrete technical description", "advantage_or_issue": "advantage|issue|stated", "confidence": 0.0-1.0}
}

Rules:
- "spec" must be CONCRETE: name the specific component, the change made, and (if mentioned) why
- Only return a spec if the article text supports a specific technical claim about the team
- If no team has a spec, return an empty JSON object: {}
- "advantage_or_issue": "advantage" if framed as a gain, "issue" if a problem, "stated" if neutral
- "confidence": 0.9+ for direct quotes, 0.6-0.8 for clear paraphrase, 0.3-0.5 for inferred, <0.2 for guesses
- Return JSON only, no prose."""

def call_llm(part_id, team_ids, context, source_url, timeout=45):
    if not OLLAMA_KEY:
        print("  ! OLLAMA_API_KEY not in env")
        return None
    if not context.strip(): return None
    if len(context) > 2500:
        context = context[:2500] + "\n\n[... truncated ...]"
    user_prompt = (
        f"Part: {part_id}\n"
        f"Teams to evaluate: {', '.join(team_ids)}\n"
        f"Source article URL: {source_url}\n\n"
        f"Article text:\n\"\"\"\n{context}\n\"\"\"\n\n"
        f"Return a JSON object keyed by team_id, containing only teams with a verifiable spec. Return JSON only, no prose."
    )
    payload = {
        "model": OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.1,
        "max_tokens": 1500,
        "response_format": {"type": "json_object"},
    }
    url = f"{OLLAMA_BASE.rstrip('/')}/chat/completions"
    last_err = None
    for attempt in range(2):
        try:
            req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={
                "Authorization": f"Bearer {OLLAMA_KEY}",
                "Content-Type": "application/json",
            })
            with urllib.request.urlopen(req, timeout=timeout) as r:
                raw = r.read()
                try:
                    body = json.loads(raw)
                except json.JSONDecodeError as e:
                    last_err = ValueError(f"response body is not JSON: {e!r} — raw[:500]={raw[:500]!r}")
                    break
                if "choices" not in body or not body["choices"]:
                    last_err = ValueError(f"no choices in response: {body!r}"[:500])
                    break
                content = body["choices"][0]["message"].get("content", "")
                if not content or not content.strip():
                    last_err = ValueError(f"empty content (model={body.get('model')}, finish={body['choices'][0].get('finish_reason')}, usage={body.get('usage')})")
                    if attempt == 0 and len(context) > 600:
                        context = context[: len(context) // 2] + "\n[... truncated ...]"
                        user_prompt = (
                            f"Part: {part_id}\n"
                            f"Teams to evaluate: {', '.join(team_ids)}\n"
                            f"Source article URL: {source_url}\n\n"
                            f"Article text:\n\"\"\"\n{context}\n\"\"\"\n\n"
                            f"Return a JSON object keyed by team_id. Return JSON only, no prose."
                        )
                        payload["messages"] = [
                            {"role": "system", "content": SYSTEM_PROMPT},
                            {"role": "user", "content": user_prompt},
                        ]
                        continue
                    break
                try:
                    return json.loads(content)
                except json.JSONDecodeError as e:
                    # Try stripping ```json``` code fences (the model
                    # sometimes wraps its output even with
                    # response_format=json_object).
                    stripped = re.sub(r'^```(?:json)?\s*\n?', '', content.strip())
                    stripped = re.sub(r'\n?```\s*$', '', stripped)
                    try:
                        return json.loads(stripped)
                    except json.JSONDecodeError:
                        pass
                    last_err = ValueError(f"content not JSON: {e!r} — content[:300]={content[:300]!r}")
                    if attempt == 0 and len(context) > 600:
                        context = context[: len(context) // 2] + "\n[... truncated ...]"
                        user_prompt = (
                            f"Part: {part_id}\n"
                            f"Teams to evaluate: {', '.join(team_ids)}\n"
                            f"Source article URL: {source_url}\n\n"
                            f"Article text:\n\"\"\"\n{context}\n\"\"\"\n\n"
                            f"Return a JSON object keyed by team_id. Return JSON only, no prose."
                        )
                        payload["messages"] = [
                            {"role": "system", "content": SYSTEM_PROMPT},
                            {"role": "user", "content": user_prompt},
                        ]
                        continue
                    break
        except json.JSONDecodeError as e:
            last_err = e
            if attempt == 0 and len(context) > 800:
                context = context[: len(context) // 2] + "\n[... truncated ...]"
                user_prompt = (
                    f"Part: {part_id}\n"
                    f"Teams to evaluate: {', '.join(team_ids)}\n"
                    f"Source article URL: {source_url}\n\n"
                    f"Article text:\n\"\"\"\n{context}\n\"\"\"\n\n"
                    f"Return a JSON object keyed by team_id. Return JSON only, no prose."
                )
                payload["messages"] = [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ]
            else:
                break
        except Exception as e:
            # On timeout, retry once with shorter context
            last_err = e
            if attempt == 0 and len(context) > 600:
                context = context[: len(context) // 2] + "\n[... truncated ...]"
                user_prompt = (
                    f"Part: {part_id}\n"
                    f"Teams to evaluate: {', '.join(team_ids)}\n"
                    f"Source article URL: {source_url}\n\n"
                    f"Article text:\n\"\"\"\n{context}\n\"\"\"\n\n"
                    f"Return a JSON object keyed by team_id. Return JSON only, no prose."
                )
                payload["messages"] = [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ]
            else:
                break
    print(f"  ! LLM call failed: {last_err!r}")
    return None

# === MAIN ===
def main():
    if not OLLAMA_KEY:
        print("FATAL: OLLAMA_API_KEY not in env")
        return 1
    print(f"[{datetime.now(timezone.utc).isoformat()}] full-scrape starting (model={OLLAMA_MODEL})")

    # === Sources ===
    SEED_PRESS = [
        {"url": "https://www.the-race.com/formula-1/f1-2026-monaco-grand-prix-everything-we-learned/", "outlet": "The Race", "date": "2026-06-08"},
        {"url": "https://www.the-race.com/formula-1/f1-2026-monaco-grand-prix-winners-losers/", "outlet": "The Race", "date": "2026-06-07"},
        {"url": "https://www.formula1.com/en/latest/article/explained-2026-aerodynamic-regulations-fia-x-mode-z-mode-.26c1CtOzCmN3GfLMywrgb2", "outlet": "Formula1.com", "date": "2024-06-06"},
        {"url": "https://www.formula1.com/en/latest/article/explained-the-new-key-terms-for-formula-1s-new-for-2026-rules.3T5BU6TC9quGcIpGzoWkY0", "outlet": "Formula1.com", "date": "2025-12-17"},
        {"url": "https://en.wikipedia.org/wiki/2026_Formula_One_World_Championship", "outlet": "Wikipedia", "date": "2026-06-08"},
        {"url": "https://www.the-race.com/formula-1/f1-reveals-2026-car-everything-you-need-to-know/", "outlet": "The Race", "date": "2024-06-06"},
    ]
    PLANETF1 = [
        "https://www.planetf1.com/news/charles-leclerc-brake-issues-ferrari-follows-lewis-hamilton-switch",
        "https://www.planetf1.com/news/adrian-newey-aston-martin-amr26-fifth-fastest-chassis",
        "https://www.planetf1.com/news/monaco-grand-prix-winners-losers-kimi-antonelli-george-russell",
        "https://www.planetf1.com/news/lance-stroll-monaco-incident-kimi-antonelli-charles-leclerc-penalty",
        "https://www.planetf1.com/news/george-russell-spain-pain-lewis-hamilton-inspector",
        "https://www.planetf1.com/news/max-verstappen-barcelona-prediction-surprising-hopes",
    ]
    RACEFANS_2026 = [
        "https://www.racefans.net/2026/04/20/sprint-races-may-delay-fixes-to-2026-f1-rules-permane/",
        "https://www.racefans.net/2026/01/13/doohan-exits-alpine-eight-months-after-being-dropped-f",
        "https://www.racefans.net/2026/01/12/williams-names-martins-as-f1-test-and-development-driv",
    ]
    F1TECH_2026 = [
        "32427", "32419", "32414", "32417", "32104", "32355", "32486", "32480", "32457", "32468", "30846",  # f=15 team threads
        "32459", "32455", "32452", "32460", "32454", "32458", "32462", "32453", "32456", "32463", "32492",  # f=12 car threads
        "31296", "30000", "32001", "32503", "32563", "32564",                                          # f=6 reg threads
        "23688", "21958", "31159", "32551", "29581", "32518",                                           # f=4 PU threads
        "32569", "32478", "32400", "31021",                                                              # additional 2026-relevant
    ]
    # Team hints for f1tech threads (so the LLM only gets 1 team for team-specific threads)
    F1TECH_TEAM_HINT = {
        "32427": "mercedes", "32419": "ferrari", "32414": "mclaren", "32417": "red_bull",
        "32104": "aston_martin", "32355": "audi", "32486": "alpine", "32480": "williams",
        "32457": "rb", "32468": "haas", "30846": "cadillac",
        "32459": "mercedes", "32455": "ferrari", "32452": "red_bull", "32460": "aston_martin",
        "32454": "audi", "32458": "alpine", "32462": "williams", "32453": "rb",
        "32456": "haas", "32463": "cadillac", "32492": "mclaren",
        "23688": "mercedes", "21958": "ferrari", "31159": "red_bull", "32551": "audi",
    }

    # === Fetch all sources ===
    articles = {}  # url -> {"text": ..., "meta": ...}
    crawled = failed = 0

    print("\n--- fetching seed press articles ---")
    for art in SEED_PRESS:
        html = fetch(art["url"])
        if not html: failed += 1; print(f"  ✗ {art['url']}"); continue
        text = html_to_text(html)
        articles[art["url"]] = {"text": text, "meta": art}
        crawled += 1
        print(f"  ✓ {len(text)}c  {art['outlet']:14s}  {art['url'][-60:]}")

    print("\n--- fetching planetf1 articles ---")
    for url in PLANETF1:
        html = fetch(url)
        if not html: failed += 1; print(f"  ✗ {url}"); continue
        # planetf1 articles use <p> for body
        paragraphs = re.findall(r'<p[^>]*>(.*?)</p>', html, re.DOTALL)
        text_paragraphs = []
        for p in paragraphs:
            t = re.sub(r'<[^>]+>', ' ', p)
            t = re.sub(r'\s+', ' ', t).strip()
            if 40 < len(t) < 2000:
                text_paragraphs.append(t)
        if not text_paragraphs: failed += 1; print(f"  ✗ {url} (no paragraphs)"); continue
        text = "\n\n".join(text_paragraphs[:40])
        articles[url] = {"text": text, "meta": {"url": url, "outlet": "PlanetF1", "date": "2026-06-10"}}
        crawled += 1
        print(f"  ✓ {len(text_paragraphs)} paragraphs, {len(text)}c  {url[-60:]}")

    print("\n--- fetching racefans 2026 articles ---")
    for url in RACEFANS_2026:
        html = fetch(url)
        if not html: failed += 1; print(f"  ✗ {url}"); continue
        paragraphs = re.findall(r'<p[^>]*>(.*?)</p>', html, re.DOTALL)
        text_paragraphs = []
        for p in paragraphs:
            t = re.sub(r'<[^>]+>', ' ', p)
            t = re.sub(r'\s+', ' ', t).strip()
            if 40 < len(t) < 2000:
                text_paragraphs.append(t)
        if not text_paragraphs: failed += 1; print(f"  ✗ {url} (no paragraphs)"); continue
        text = "\n\n".join(text_paragraphs[:40])
        articles[url] = {"text": text, "meta": {"url": url, "outlet": "RaceFans", "date": "2026-01-12"}}
        crawled += 1
        print(f"  ✓ {len(text_paragraphs)} paragraphs, {len(text)}c  {url[-60:]}")

    print("\n--- fetching f1technical threads ---")
    for tid in F1TECH_2026:
        url = f"https://www.f1technical.net/forum/viewtopic.php?t={tid}"
        html = fetch(url)
        if not html: failed += 1; print(f"  ✗ t={tid}"); continue
        matches = re.findall(r'class="content"[^>]*>(.*?)</div>\s*</div>\s*</div>', html, re.DOTALL)
        posts = []
        for p in matches:
            t = re.sub(r'<[^>]+>', ' ', p)
            t = re.sub(r'\s+', ' ', t).strip()
            if 30 < len(t) < 5000:
                posts.append(t)
        if not posts: continue
        text = "\n\n---\n\n".join(posts[:15])
        team_hint = F1TECH_TEAM_HINT.get(tid, "general")
        articles[url] = {
            "text": text,
            "meta": {
                "url": url, "outlet": "F1 Technical", "date": "2026-06-10",
                "team": team_hint, "kind": "forum",
            }
        }
        crawled += 1
        print(f"  ✓ t={tid} team={team_hint:13s} {len(posts)} posts  {len(text)}c")

    print(f"\n--- fetch summary: {crawled} sources OK, {failed} failed ---")

    # === Build (article, part) pairs ===
    article_part_pairs = []
    for url, art in articles.items():
        if not art["text"]: continue
        meta = art["meta"]
        for part_id in ALL_PARTS:
            # Find sentences mentioning this part
            part_sentences = []
            for s in split_sentences(art["text"]):
                if part_in_text(s, part_id):
                    part_sentences.append(s)
            if not part_sentences: continue
            joined = "\n\n".join(part_sentences)
            if len(joined) > 2500:
                joined = joined[:2500] + "\n\n[... truncated ...]"
            article_part_pairs.append((url, part_id, joined, meta))

    print(f"--- {len(article_part_pairs)} (article, part) pairs to send to LLM ---")

    # === LLM extraction ===
    best_specs = {}  # (team_id, part_id) -> spec dict
    pairs_processed = 0
    calls = accepted = rejected = no_specs = 0

    # Sort: process press articles first (richer content, higher yield),
    # then f1tech. Within each, process (article, part) pairs in
    # order of sentence-match length (more signal = higher priority).
    def pair_score(p):
        url, part_id, context, meta = p
        # Press > f1tech; longer context > shorter
        kind_score = 1 if meta.get("kind") != "forum" else 0
        return (kind_score, len(context))

    sorted_pairs = sorted(article_part_pairs, key=pair_score, reverse=True)

    for url, part_id, context, meta in sorted_pairs:
        # Team hint: for f1tech team threads, only the hinted team
        if meta.get("kind") == "forum" and meta.get("team") in ALL_TEAMS:
            team_hint = [meta["team"]]
        else:
            team_hint = ALL_TEAMS
        # Skip if this (team, part) pair is already well-served
        # (i.e. we already have a high-confidence spec for ALL teams
        # this call could return). For per-team f1tech threads this
        # is a no-op.
        skip = True
        for t in team_hint:
            if (t, part_id) not in best_specs or best_specs[(t, part_id)]["confidence"] < 0.8:
                skip = False
                break
        if skip and len(team_hint) > 1:
            continue  # already have good coverage for this part across all teams
        per_team = call_llm(part_id, team_hint, context, url)
        calls += 1
        pairs_processed += 1
        # Small pacing to avoid rate limits / cascading timeouts
        time.sleep(0.5)
        if not per_team:
            no_specs += 1
            print(f"    × LLM returned no specs (call #{calls})", flush=True)
            continue
        accepted_this_call = 0
        rejected_this_call = 0
        for team_id, spec in per_team.items():
            if team_id not in ALL_TEAMS: continue
            if not spec or "spec" not in spec: continue
            spec_text = str(spec.get("spec", "")).strip()
            if not (20 <= len(spec_text) <= 600):
                rejected += 1; rejected_this_call += 1; continue
            if not team_in_text(spec_text, team_id):
                rejected += 1; rejected_this_call += 1; continue
            if not part_in_text(spec_text, part_id):
                rejected += 1; rejected_this_call += 1; continue
            try:
                conf = float(spec.get("confidence", 0.0))
            except: conf = 0.0
            if conf < 0.30:
                rejected += 1; rejected_this_call += 1; continue
            aoi = spec.get("advantage_or_issue", "stated")
            if aoi not in ("advantage", "issue", "stated"): aoi = "stated"
            key = (team_id, part_id)
            if key not in best_specs or conf > best_specs[key]["confidence"]:
                best_specs[key] = {
                    "team_id": team_id, "part_id": part_id,
                    "spec": spec_text, "advantage_or_issue": aoi, "confidence": conf,
                    "source": {
                        "outlet": meta.get("outlet", ""),
                        "author": meta.get("author", ""),
                        "date":   meta.get("date", ""),
                        "url":    url,
                    },
                }
                accepted += 1; accepted_this_call += 1
            else:
                rejected += 1; rejected_this_call += 1
        print(f"    + call #{calls}: {accepted_this_call} accepted, {rejected_this_call} rejected, {len(per_team)} teams returned", flush=True)

    specs = sorted(best_specs.values(), key=lambda s: (s["team_id"], s["part_id"]))

    # === Write output ===
    output = {
        "schema_version":  2,
        "generated_utc":   datetime.now(timezone.utc).isoformat(),
        "methodology":     (
            "Full-pipeline run combining press articles (The Race, Formula1.com, Wikipedia, PlanetF1, RaceFans) "
            "and f1technical.net forum threads. Each (article, part) pair sent to minimax-m3 for LLM extraction. "
            "Spec is kept only if (a) LLM confidence >= 0.30, (b) spec text contains the team name and part name, "
            "(c) spec is 20-600 chars. Best spec per (team, part) pair retained."
        ),
        "llm":             {"provider": "ollama-cloud", "model": OLLAMA_MODEL},
        "sources_crawled": crawled,
        "sources_failed":  failed,
        "calls":           calls,
        "specs":           specs,
    }
    out_path = "/root/.hermes/workspace/projects/f1-2026-viewer/data/team-part-specs.json"
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\n[{datetime.now(timezone.utc).isoformat()}] DONE")
    print(f"  calls:      {calls}")
    print(f"  accepted:   {accepted}")
    print(f"  rejected:   {rejected}")
    print(f"  no_specs:   {no_specs}")
    print(f"  specs out:  {len(specs)}")
    print(f"  teams:      {len(set(s['team_id'] for s in specs))}")
    print(f"  parts:      {len(set(s['part_id'] for s in specs))}")
    print(f"  output:     {out_path}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
