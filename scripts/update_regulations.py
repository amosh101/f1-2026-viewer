#!/usr/bin/env python3
"""
update_regulations.py — yearly updater for data/regulations.json

USAGE
-----
    # Add a new year (e.g. when FIA publishes 2027 regulations):
    python3 scripts/update_regulations.py --add-year 2027

    # Validate the existing regulations.json (no changes):
    python3 scripts/update_regulations.py --validate

    # Print a summary of all years documented:
    python3 scripts/update_regulations.py --summary

WHAT IT DOES
------------
1. --validate: parses regulations.json, checks schema_version, counts years
   and changes per category, asserts every change has source_url + source_label
   + impact list. Exits non-zero on validation failure.
2. --add-year YEAR: reads regulations.json, adds a new empty year entry with
   TODO markers for each category. The year is added with `active: false` and
   regulation_pct: 0 — must be hand-edited (or scraped from FIA) to fill in.
3. --summary: prints a one-line per year summary (year, % rewrite, # changes,
   # categories). Useful for the weekly check.

WHY NOT SCRAPE FIA
------------------
The FIA publishes regulation documents as PDFs (one per Article range). There
is no public FIA regulations API. The community resources (FIA Technical
Regulations portal, RaceFans/F1/F1Technical.net journalism) need human
interpretation — a scraper would either hallucinate articles or miss nuance.
For a "yearly update", the workflow is: read the FIA regulation summary
(https://www.fia.com/regulation/category/110), identify which Articles changed
substantively, write the entries by hand. This script supports that workflow
without pretending to automate what requires expert judgment.

The change_pct field on each entry is OPTIONAL (null when the change is
qualitative, e.g. "MGU-H removed" is -100% but "X-Mode replaces DRS" is null
because it's a rule replacement, not a numeric delta). The headline
value_pct is hand-set by the editor based on FIA's own characterisation
("biggest rewrite in 40 years" → 70%).

EXIT CODES
----------
0  success
1  validation failure
2  file not found
3  invalid argument
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REG_PATH = os.path.join(ROOT, "data", "regulations.json")

REQUIRED_CHANGE_KEYS = {
    "id", "title", "summary", "change_pct", "change_pct_label",
    "source_label", "source_url", "impact",
}
CATEGORIES = ["aero", "power_unit", "chassis", "sporting"]


def load():
    if not os.path.exists(REG_PATH):
        print(f"[err] {REG_PATH} not found", file=sys.stderr)
        sys.exit(2)
    with open(REG_PATH) as f:
        return json.load(f)


def save(data):
    with open(REG_PATH, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
    print(f"[ok] wrote {REG_PATH}")


def validate(data):
    """Return list of error strings (empty list = valid)."""
    errs = []
    if "schema_version" not in data:
        errs.append("missing top-level 'schema_version'")
    if "headline" not in data:
        errs.append("missing top-level 'headline'")
    else:
        h = data["headline"]
        for k in ("label", "value_pct", "subtitle", "source", "source_url"):
            if k not in h:
                errs.append(f"headline missing '{k}'")
    if "years" not in data or not isinstance(data["years"], dict):
        errs.append("missing or non-dict 'years'")
        return errs
    for yr, yr_data in data["years"].items():
        if "regulation_pct" not in yr_data:
            errs.append(f"year {yr}: missing 'regulation_pct'")
        if "summary" not in yr_data:
            errs.append(f"year {yr}: missing 'summary'")
        if "source_label" not in yr_data or "source_url" not in yr_data:
            errs.append(f"year {yr}: missing source_label or source_url")
        if "categories" not in yr_data:
            errs.append(f"year {yr}: missing 'categories'")
            continue
        for cat_key, cat in yr_data["categories"].items():
            if "label" not in cat:
                errs.append(f"{yr}/{cat_key}: missing 'label'")
            if "changes" not in cat or not isinstance(cat["changes"], list):
                errs.append(f"{yr}/{cat_key}: missing or non-list 'changes'")
                continue
            for ch in cat["changes"]:
                missing = REQUIRED_CHANGE_KEYS - ch.keys()
                if missing:
                    errs.append(f"{yr}/{cat_key}/{ch.get('id', '?')}: missing {sorted(missing)}")
                if "impact" in ch and not isinstance(ch["impact"], list):
                    errs.append(f"{yr}/{cat_key}/{ch.get('id', '?')}: 'impact' must be a list")
    return errs


def cmd_validate():
    data = load()
    errs = validate(data)
    if errs:
        print(f"[FAIL] {len(errs)} validation errors:", file=sys.stderr)
        for e in errs:
            print(f"  - {e}", file=sys.stderr)
        sys.exit(1)
    yr_count = len(data["years"])
    ch_total = sum(
        len(cat["changes"])
        for yr in data["years"].values()
        for cat in yr.get("categories", {}).values()
    )
    print(f"[ok] regulations.json: schema v{data.get('schema_version')}, "
          f"{yr_count} years, {ch_total} total changes, headline "
          f"+{data['headline']['value_pct']}%")


def cmd_add_year(year):
    if not year.isdigit() or len(year) != 4:
        print(f"[err] year must be 4 digits, got {year!r}", file=sys.stderr)
        sys.exit(3)
    data = load()
    if year in data["years"]:
        print(f"[err] year {year} already in regulations.json", file=sys.stderr)
        sys.exit(1)
    # Scaffold an empty year with TODO markers in every category.
    new_year = {
        "active": False,
        "regulation_pct": 0,
        "summary": f"TODO: {year} regulation summary. Read the FIA Technical "
                   f"Regulations portal (https://www.fia.com/regulation/category/110) "
                   f"and add a 1-2 sentence summary of the {year} rules.",
        "source_label": f"FIA — {year} Technical Regulations",
        "source_url": "https://www.fia.com/regulation/category/110",
        "categories": {},
    }
    for cat_key in CATEGORIES:
        new_year["categories"][cat_key] = {
            "label": cat_key.replace("_", " ").upper(),
            "changes": [],  # empty — to be filled
        }
    data["years"][year] = new_year
    save(data)
    print(f"[ok] added year {year} with {len(CATEGORIES)} empty categories")
    print(f"     fill in each category's 'changes' list with the {year} FIA articles")
    print(f"     set 'active: true' on the year once {year} begins")
    print(f"     update 'headline.value_pct' if the {year} rules are a major rewrite")


def cmd_summary():
    data = load()
    if not data.get("years"):
        print("[warn] no years documented")
        return
    print(f"{'YEAR':<6} {'%':<5} {'ACTIVE':<7} {'CHANGES':<8} CATEGORIES")
    print("-" * 60)
    for yr in sorted(data["years"].keys(), reverse=True):
        y = data["years"][yr]
        ch = sum(len(c.get("changes", [])) for c in y.get("categories", {}).values())
        cats = list(y.get("categories", {}).keys())
        print(f"{yr:<6} {y.get('regulation_pct', 0):<5} "
              f"{'YES' if y.get('active') else 'no':<7} {ch:<8} {','.join(cats)}")
    h = data.get("headline", {})
    print(f"\nheadline: +{h.get('value_pct', '?')}% — {h.get('label', '?')}")
    print(f"source:   {h.get('source', '?')}")


def main():
    p = argparse.ArgumentParser(description="Yearly updater for data/regulations.json")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--validate", action="store_true", help="validate the file")
    g.add_argument("--add-year", metavar="YEAR", help="add a new year scaffold")
    g.add_argument("--summary", action="store_true", help="print year summary")
    args = p.parse_args()
    if args.validate:
        cmd_validate()
    elif args.add_year:
        cmd_add_year(args.add_year)
    elif args.summary:
        cmd_summary()


if __name__ == "__main__":
    main()
