#!/usr/bin/env python3
"""Re-check ads already in entry.json against a fresh Indeed lookup.

Usage: python3 tools/entry_recheck.py LOOKUP_FILE [LOOKUP_FILE ...]

LOOKUP_FILE = saved get-dataset-items output from a kaix/indeed-scraper run in
lookup mode ({"jobKeys": [...]}), fetched with
fields "id,title.text,description.text,signals.isExpired".

Drops: ads Indeed marks expired, ads whose full text asks for prior experience
or a professional qualification already held, ads not found in the lookup, and
LinkedIn job ads (they cannot be looked up). LinkedIn graduate-programme ads
(type "scheme") are kept.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import entry_build as eb  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main(paths):
    look = {}
    for p in paths:
        d = json.load(open(p))
        for i in (d["items"] if isinstance(d, dict) else d):
            look[i["id"]] = i
    path = os.path.join(ROOT, "entry.json")
    feed = json.load(open(path))
    stats = {"kept": 0, "expired": 0, "experience": 0, "notfound": 0, "linkedin_job": 0}
    out = []
    for r in feed["roles"]:
        key = r["id"][3:]
        if key.startswith("li"):
            if r.get("type") == "scheme":
                out.append(r)
                stats["kept"] += 1
            else:
                stats["linkedin_job"] += 1
            continue
        i = look.get(key)
        if not i:
            stats["notfound"] += 1
            continue
        if i.get("signals.isExpired") or (i.get("signals") or {}).get("isExpired"):
            stats["expired"] += 1
            continue
        text = i.get("description.text") or (i.get("description") or {}).get("text") or ""
        yrs = eb.min_years(text)
        if (yrs is not None and yrs >= 1) or eb.needs_experience(text) or (
                eb.PQE_RE.search(text) and not re.search(r"trainee|paralegal|assistant", r["title"], re.I)):
            stats["experience"] += 1
            continue
        r.pop("notes", None) if "year's experience" in r.get("notes", "") else None
        out.append(r)
        stats["kept"] += 1
    feed["roles"] = out
    json.dump(feed, open(path, "w"), ensure_ascii=False, separators=(",", ":"))
    print(json.dumps(stats))


if __name__ == "__main__":
    main(sys.argv[1:])
