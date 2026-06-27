"""
build_db.py
-----------
Scans `sources/` for canonical JSON files, resolves mission IDs to ACAT IDs,
and builds catalog.db.

Resolution order:
  1. overrides.csv  -- manual corrections always win
  2. TIC crossmatch -- KIC/EPIC → TIC via MAST TIC v8 (batch queries)
  3. SIMBAD         -- fallback for HD/HIP/other identifiers
  4. Unresolved     -- acat_id left NULL, conflict written to build.log

Run:
    python scripts/build_db.py [--sources-dir sources] [--db catalog.db]
                               [--overrides overrides.csv] [--log build.log]
                               [--no-resolve]
"""

import argparse
import csv
import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from astropy.table import vstack
from astroquery.mast import Catalogs
from astroquery.simbad import Simbad

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

SCHEMA = """
CREATE TABLE IF NOT EXISTS targets (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    acat_id     TEXT,                   -- e.g. "ACAT000000001"
    catalog_id  TEXT NOT NULL,          -- e.g. "TIC_12345678"
    mission     TEXT NOT NULL,          -- "TIC", "KIC", "EPIC", ...
    mission_id  INTEGER NOT NULL,
    source      TEXT NOT NULL,          -- "Hatt+2023", "Sayeed+2024", ...
    numax       REAL,
    e_numax     REAL,
    teff        REAL,
    e_teff      REAL
);

CREATE INDEX IF NOT EXISTS idx_acat_id    ON targets(acat_id);
CREATE INDEX IF NOT EXISTS idx_catalog_id ON targets(catalog_id);
CREATE INDEX IF NOT EXISTS idx_mission_id ON targets(mission_id);
CREATE INDEX IF NOT EXISTS idx_source     ON targets(source);
CREATE INDEX IF NOT EXISTS idx_numax      ON targets(numax);
CREATE INDEX IF NOT EXISTS idx_teff       ON targets(teff);
"""

MAST_BATCH  = 1000
ACAT_FMT    = "ACAT{:09d}"

# Normalise mission name variants to canonical forms
MISSION_ALIASES = {
    "kic":  "KIC",  "kplr": "KIC",
    "epic": "EPIC",
    "tic":  "TIC",  "tess": "TIC",
    "hd":   "HD",   "hip":  "HIP",
}


def normalise_mission(raw: str) -> str:
    return MISSION_ALIASES.get(raw.lower(), raw.upper())


# ---------------------------------------------------------------------------
# Overrides
# ---------------------------------------------------------------------------

def load_overrides(path: Path) -> dict[str, str]:
    """
    Returns {catalog_id: canonical_id} from overrides.csv.

    CSV format (no header):
        KIC_1234567, TIC_9876543
        EPIC_211xxxxx, TIC_8888888
    """
    overrides = {}
    if not path.exists():
        return overrides
    with open(path, newline="") as f:
        for row in csv.reader(f):
            if len(row) >= 2 and not row[0].strip().startswith("#"):
                overrides[row[0].strip()] = row[1].strip()
    return overrides


# ---------------------------------------------------------------------------
# MAST TIC crossmatch  (KIC / EPIC → TIC)
# ---------------------------------------------------------------------------

def _chunks(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i : i + n]


def resolve_via_mast(
    mission: str,
    mission_ids: list[int],
    log: logging.Logger,
) -> dict[int, int]:
    """
    Query MAST TIC v8 for KIC or EPIC IDs and return {mission_id: tic_id}.
    TIC targets resolve to themselves.
    """
    if mission == "TIC":
        return {mid: mid for mid in mission_ids}

    col = {"KIC": "KIC", "EPIC": "EPIC"}.get(mission)
    if col is None:
        return {}

    result = {}
    n_batches = -(-len(mission_ids) // MAST_BATCH)
    for i, chunk in enumerate(_chunks(mission_ids, MAST_BATCH)):
        log.info(f"  MAST {mission} batch {i+1}/{n_batches} ({len(chunk)} IDs)...")
        try:
            t = Catalogs.query_criteria(catalog="Tic", **{col: chunk})
            if t is None or len(t) == 0:
                continue
            for row in t:
                try:
                    mid = int(row[col])
                    tic = int(row["ID"])
                    if mid in result and result[mid] != tic:
                        log.warning(
                            f"CONFLICT: {mission}_{mid} matches multiple TIC IDs "
                            f"({result[mid]}, {tic}) — skipping"
                        )
                        result[mid] = None   # mark as conflicted
                    else:
                        result[mid] = tic
                except (ValueError, TypeError):
                    continue
        except Exception as exc:
            log.error(f"  MAST batch {i+1} failed: {exc}")

    return result


# ---------------------------------------------------------------------------
# SIMBAD fallback
# ---------------------------------------------------------------------------

def resolve_via_simbad(
    catalog_ids: list[str],
    log: logging.Logger,
) -> dict[str, str]:
    """
    Query SIMBAD for a list of catalog_ids (e.g. 'HD_12345').
    Returns {catalog_id: simbad_main_id}.
    """
    simbad = Simbad()
    simbad.TIMEOUT = 60
    result = {}
    for cid in catalog_ids:
        # convert catalog_id back to SIMBAD identifier, e.g. "HD_12345" → "HD 12345"
        identifier = cid.replace("_", " ", 1)
        try:
            t = simbad.query_object(identifier)
            if t is not None and len(t) > 0:
                main_id = str(t["MAIN_ID"][0]).strip()
                # normalise to underscore form, e.g. "HD  12345" → "HD_12345"
                parts = main_id.split()
                result[cid] = f"{parts[0]}_{parts[-1]}" if len(parts) >= 2 else main_id
            else:
                log.warning(f"SIMBAD: no match for {identifier}")
        except Exception as exc:
            log.error(f"SIMBAD query failed for {identifier}: {exc}")
    return result


# ---------------------------------------------------------------------------
# ACAT ID assignment
# ---------------------------------------------------------------------------

def assign_acat_ids(
    canonical_ids: list[str | None],
) -> tuple[dict[str, str], int]:
    """
    Given a list of canonical IDs (e.g. 'TIC_9876', 'HD_12345', None),
    assign sequential ACAT IDs to each unique non-None canonical ID.
    Returns ({canonical_id: acat_id}, next_counter).
    """
    mapping: dict[str, str] = {}
    counter = 1
    for cid in canonical_ids:
        if cid is not None and cid not in mapping:
            mapping[cid] = ACAT_FMT.format(counter)
            counter += 1
    return mapping, counter


# ---------------------------------------------------------------------------
# Main build
# ---------------------------------------------------------------------------

def build(
    sources_dir: Path,
    db_path: Path,
    overrides_path: Path,
    log_path: Path,
    resolve: bool,
):
    # --- logging setup ---
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        handlers=[
            logging.FileHandler(log_path, mode="w"),
            logging.StreamHandler(),
        ],
    )
    log = logging.getLogger("build_db")
    log.info(f"Build started  {datetime.now(timezone.utc).isoformat()}")

    # --- load sources ---
    json_files = sorted(sources_dir.glob("*.json"))
    if not json_files:
        log.error(f"No JSON files found in {sources_dir}/")
        return

    overrides = load_overrides(overrides_path)
    if overrides:
        log.info(f"Loaded {len(overrides)} override(s) from {overrides_path}")

    # Collect all rows and group unique mission IDs by mission type
    all_rows    = []   # (catalog_id, mission, mission_id, source, numax, e_numax, teff, e_teff)
    by_mission  = {}   # {mission: set(mission_ids)}

    for jf in json_files:
        with open(jf) as f:
            data = json.load(f)
        source  = data["source"]
        mission = normalise_mission(data["mission"])
        targets = data["targets"]

        by_mission.setdefault(mission, set())
        for t in targets:
            mid        = int(t["mission_id"])
            catalog_id = f"{mission}_{mid}"
            by_mission[mission].add(mid)
            all_rows.append((
                catalog_id, mission, mid, source,
                t.get("numax"), t.get("e_numax"),
                t.get("teff"),  t.get("e_teff"),
            ))

        log.info(f"  {jf.name:40s}  {len(targets):>6d} rows  ({source})")

    log.info(f"Total rows: {len(all_rows)} across {len(json_files)} sources")

    # --- resolve canonical IDs ---
    # canonical_map: {catalog_id → canonical_id (e.g. "TIC_9876")}
    canonical_map: dict[str, str | None] = {}

    if resolve:
        # Step 1: MAST for TIC/KIC/EPIC
        for mission, ids in by_mission.items():
            if mission in ("TIC", "KIC", "EPIC"):
                log.info(f"Resolving {len(ids)} {mission} IDs via MAST...")
                mast_result = resolve_via_mast(mission, list(ids), log)
                for mid, tic_id in mast_result.items():
                    cid = f"{mission}_{mid}"
                    if tic_id is None:
                        canonical_map[cid] = None   # conflict flagged above
                    else:
                        canonical_map[cid] = f"TIC_{tic_id}"

        # Step 2: SIMBAD fallback for remaining missions (HD, HIP, etc.)
        simbad_ids = [
            f"{mission}_{mid}"
            for mission, ids in by_mission.items()
            if mission not in ("TIC", "KIC", "EPIC")
            for mid in ids
        ]
        if simbad_ids:
            log.info(f"Resolving {len(simbad_ids)} IDs via SIMBAD...")
            simbad_result = resolve_via_simbad(simbad_ids, log)
            for cid, main_id in simbad_result.items():
                canonical_map[cid] = main_id
            for cid in simbad_ids:
                if cid not in canonical_map:
                    log.warning(f"UNRESOLVED: {cid} — acat_id will be NULL")
                    canonical_map[cid] = None

        # Step 3: apply overrides (always win)
        for cid, override_canonical in overrides.items():
            if cid in canonical_map and canonical_map[cid] != override_canonical:
                log.info(
                    f"OVERRIDE: {cid}  {canonical_map[cid]} → {override_canonical}"
                )
            canonical_map[cid] = override_canonical

    else:
        # No resolution: each catalog_id is its own canonical ID
        log.info("Skipping ID resolution (--no-resolve)")
        for row in all_rows:
            cid = row[0]
            canonical_map[cid] = cid

    # --- assign ACAT IDs ---
    acat_map, n_assigned = assign_acat_ids(list(canonical_map.values()))
    log.info(f"Assigned {n_assigned - 1} ACAT IDs")

    # --- write DB ---
    conn = sqlite3.connect(db_path)
    conn.executescript("DROP TABLE IF EXISTS targets;")
    conn.executescript(SCHEMA)

    db_rows = []
    for (catalog_id, mission, mission_id, source,
         numax, e_numax, teff, e_teff) in all_rows:
        canonical = canonical_map.get(catalog_id)
        acat_id   = acat_map.get(canonical) if canonical else None
        db_rows.append((
            acat_id, catalog_id, mission, mission_id, source,
            numax, e_numax, teff, e_teff,
        ))

    conn.executemany(
        "INSERT INTO targets "
        "(acat_id, catalog_id, mission, mission_id, source, "
        " numax, e_numax, teff, e_teff) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        db_rows,
    )
    conn.commit()
    conn.close()
    log.info(f"Written {db_path}  ({len(db_rows)} rows)")
    log.info(f"Build log: {log_path}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Build the AsteroCat SQLite database.")
    p.add_argument("--sources-dir", default="sources",      type=Path)
    p.add_argument("--db",          default="catalog.db",   type=Path)
    p.add_argument("--overrides",   default="overrides.csv",type=Path)
    p.add_argument("--log",         default="build.log",    type=Path)
    p.add_argument(
        "--no-resolve", action="store_true",
        help="Skip MAST/SIMBAD resolution (useful for offline testing)",
    )
    args = p.parse_args()
    build(args.sources_dir, args.db, args.overrides, args.log, not args.no_resolve)
