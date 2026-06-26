"""
build_db.py
-----------
Scans the `sources/` directory for canonical JSON files produced by
individual compilation scripts, then builds (or rebuilds) catalog.db.

Each JSON file must follow this schema:
{
  "source": "Hatt+2023",
  "mission": "TIC",          # e.g. "TIC", "KIC", "EPIC"
  "targets": [
    {
      "mission_id": 12345678,
      "numax":    123.4,   "e_numax":  1.2,   # null if unknown
      "teff":    5000.0,   "e_teff":  80.0,   # null if unknown
    },
    ...
  ]
}

Run:
    python build_db.py [--sources-dir sources] [--db catalog.db]
"""

import argparse
import json
import sqlite3
from pathlib import Path


SCHEMA = """
CREATE TABLE IF NOT EXISTS targets (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    catalog_id  TEXT NOT NULL,          -- e.g. "TIC_12345678"
    resolved_id TEXT,                   -- future cross-match placeholder
    mission     TEXT NOT NULL,          -- "TIC", "KIC", "EPIC", …
    mission_id  INTEGER NOT NULL,
    source      TEXT NOT NULL,          -- "Hatt+2023", "Sayeed+2024", …
    numax       REAL,
    e_numax     REAL,
    teff        REAL,
    e_teff      REAL
);

CREATE INDEX IF NOT EXISTS idx_catalog_id  ON targets(catalog_id);
CREATE INDEX IF NOT EXISTS idx_mission_id  ON targets(mission_id);
CREATE INDEX IF NOT EXISTS idx_source      ON targets(source);
CREATE INDEX IF NOT EXISTS idx_numax       ON targets(numax);
CREATE INDEX IF NOT EXISTS idx_teff        ON targets(teff);
"""


def load_json(path: Path) -> dict:
    with open(path) as f:
        return json.load(f)


def build(sources_dir: Path, db_path: Path):
    json_files = sorted(sources_dir.glob("*.json"))
    if not json_files:
        print(f"No JSON files found in {sources_dir}/")
        return

    conn = sqlite3.connect(db_path)
    conn.executescript("DROP TABLE IF EXISTS targets;")
    conn.executescript(SCHEMA)

    total = 0
    for jf in json_files:
        data = load_json(jf)
        source  = data["source"]
        mission = data["mission"].upper()
        rows = []
        for t in data["targets"]:
            mid = int(t["mission_id"])
            catalog_id = f"{mission}_{mid}"
            rows.append((
                catalog_id,
                None,           # resolved_id placeholder
                mission,
                mid,
                source,
                t.get("numax"),
                t.get("e_numax"),
                t.get("teff"),
                t.get("e_teff"),
            ))
        conn.executemany(
            "INSERT INTO targets "
            "(catalog_id, resolved_id, mission, mission_id, source, "
            " numax, e_numax, teff, e_teff) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            rows,
        )
        print(f"  {jf.name:40s}  {len(rows):>6d} rows  ({source})")
        total += len(rows)

    conn.commit()
    conn.close()
    print(f"\nBuilt {db_path}  —  {total} rows from {len(json_files)} sources.")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--sources-dir", default="sources", type=Path)
    p.add_argument("--db",          default="catalog.db", type=Path)
    args = p.parse_args()
    build(args.sources_dir, args.db)
