#!/usr/bin/env python3
"""One-time converter: RE Activity Log CSV -> app log entries JSON.

Maps the CSV columns to the rep-pwa log entry shape:
  { id, date, endDate, category, activities[], properties[], description, notes,
    durationMs, method:"import", wk }

Run: python3 scripts/csv_to_logs.py "<csv path>" > scripts/import_logs.json
"""
import csv, json, sys, hashlib
from datetime import date

# CSV CATEGORY label -> app category id (see CATEGORIES in App.jsx)
CAT_MAP = {
    "Acquisitions & Dispositions": "acquisition",
    "Maintenance & Repairs":       "development",
    "Leasing & Tenants":           "management",
    "Financial & Admin":           "finance",
    "Legal & Compliance":          "legal",
    "Education & Research":         "education",
}

def week_key(d: str) -> str:
    """Mirror weekKey() in App.jsx (JS getDay = 0..6, Sun=0)."""
    y, m, dd = map(int, d.split("-"))
    dt = date(y, m, dd)
    jan1 = date(y, 1, 1)
    days = (dt - jan1).days
    js_dow = (dt.weekday() + 1) % 7  # python Mon=0 -> JS Sun=0
    import math
    wk = math.ceil((days + js_dow + 1) / 7)
    return f"{y}-W{wk:02d}"

def main(path):
    out = []
    seen = set()
    props = set()
    skipped = 0
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            start = (r.get("START_DATE") or "").strip()
            if not start:
                skipped += 1
                continue
            cat_label = (r.get("CATEGORY") or "").strip()
            category = CAT_MAP.get(cat_label, "management")
            activities = [a.strip() for a in (r.get("ACTIVITIES") or "").split(";") if a.strip()]
            properties = [p.strip() for p in (r.get("PROPERTIES") or "").split(";") if p.strip()]
            for p in properties:
                props.add(p)
            try:
                hours = int(float(r.get("HOURS") or 0))
                minutes = int(float(r.get("MINUTES") or 0))
            except ValueError:
                hours, minutes = 0, 0
            duration_ms = (hours * 60 + minutes) * 60000
            desc = (r.get("DESCRIPTION_OF_WORK_DONE") or "").strip()
            notes = (r.get("ADDITIONAL_NOTES") or "").strip()
            end = (r.get("END_DATE") or "").strip()

            # Stable dedupe key so re-running can't double-insert.
            key = "|".join([start, cat_label, "/".join(activities), "/".join(properties), desc, str(duration_ms)])
            h = hashlib.md5(key.encode()).hexdigest()
            if h in seen:
                skipped += 1
                continue
            seen.add(h)

            out.append({
                "id": "imp_" + h[:16],
                "date": start,
                "endDate": end,
                "category": category,
                "activities": activities,
                "properties": properties,
                "description": desc,
                "notes": notes,
                "durationMs": duration_ms,
                "method": "import",
                "wk": week_key(start),
            })

    out.sort(key=lambda e: e["date"], reverse=True)
    total_ms = sum(e["durationMs"] for e in out)
    sys.stderr.write(f"entries={len(out)} skipped={skipped} total_hours={total_ms/3600000:.2f}\n")
    sys.stderr.write("distinct properties:\n  " + "\n  ".join(sorted(props)) + "\n")
    print(json.dumps(out, ensure_ascii=False))

if __name__ == "__main__":
    main(sys.argv[1])
