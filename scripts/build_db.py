"""
build_db.py
-----------
Scans `sources/` for canonical JSON files, resolves mission IDs to ACAT IDs,
and builds catalog.db.

Resolution order:
  1. Cache       -- sources whose JSON hash matches the DB are skipped entirely
  2. overrides.csv -- manual corrections always win
  3. TIC crossmatch -- KIC/EPIC → TIC via MAST TIC v8 (batch queries)
  4. SIMBAD      -- fallback for HD/HIP/other identifiers
  5. Unresolved  -- acat_id left NULL, conflict written to build.log

Run:
    python scripts/build_db.py [--sources-dir sources] [--db catalog.db]
                               [--overrides overrides.csv] [--log build.log]
                               [--no-resolve] [--force source_name]
"""

import argparse
import csv
import hashlib
import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from astroquery.mast import Catalogs
from astroquery.simbad import Simbad

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

TARGETS_SCHEMA = """
CREATE TABLE IF NOT EXISTS targets (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    acat_id     TEXT,
    catalog_id  TEXT NOT NULL,
    mission     TEXT NOT NULL,
    instrument  TEXT NOT NULL,
    mission_id  INTEGER NOT NULL,
    source      TEXT NOT NULL,
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

SOURCES_SCHEMA = """
CREATE TABLE IF NOT EXISTS source_cache (
    source      TEXT PRIMARY KEY,
    json_hash   TEXT NOT NULL,
    date_added  TEXT NOT NULL
);
"""

MAST_BATCH = 1000
ACAT_FMT   = "ACAT{:09d}"

MISSION_ALIASES = {
    "kic": "KIC", "kplr": "KIC",
    "epic": "EPIC",
    "tic": "TIC", "tess": "TIC",
    "hd": "HD", "hip": "HIP",
}

MISSION_TO_INSTRUMENT = {
    "TIC":  "TESS",
    "KIC":  "Kepler",
    "EPIC": "K2",
}

def mission_to_instrument(mission: str) -> str:
    return MISSION_TO_INSTRUMENT.get(mission, mission)


def normalise_mission(raw: str) -> str:
    return MISSION_ALIASES.get(raw.lower(), raw.upper())


# ---------------------------------------------------------------------------
# JSON hashing
# ---------------------------------------------------------------------------

def md5(path: Path) -> str:
    h = hashlib.md5()
    h.update(path.read_bytes())
    return h.hexdigest()


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------

def load_cache(conn: sqlite3.Connection) -> dict[str, str]:
    """Return {source: json_hash} for all cached sources."""
    try:
        rows = conn.execute("SELECT source, json_hash FROM source_cache").fetchall()
        return {r[0]: r[1] for r in rows}
    except sqlite3.OperationalError:
        return {}


def load_cached_rows(conn: sqlite3.Connection, source: str) -> list[tuple]:
    """Return existing target rows for a cached source."""
    rows = conn.execute(
        "SELECT acat_id, catalog_id, mission, instrument, mission_id, source, "
        "       numax, e_numax, teff, e_teff "
        "FROM targets WHERE source = ?", (source,)
    ).fetchall()
    return [tuple(r) for r in rows]


def update_cache(conn: sqlite3.Connection, source: str, json_hash: str):
    conn.execute(
        "INSERT OR REPLACE INTO source_cache (source, json_hash, date_added) "
        "VALUES (?, ?, ?)",
        (source, json_hash, datetime.now(timezone.utc).isoformat()),
    )


# ---------------------------------------------------------------------------
# Overrides
# ---------------------------------------------------------------------------

def load_overrides(path: Path) -> dict[str, str]:
    overrides = {}
    if not path.exists():
        return overrides
    with open(path, newline="") as f:
        for row in csv.reader(f):
            if len(row) >= 2 and not row[0].strip().startswith("#"):
                overrides[row[0].strip()] = row[1].strip()
    return overrides


# ---------------------------------------------------------------------------
# MAST TIC crossmatch
# ---------------------------------------------------------------------------

def _chunks(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i : i + n]


def resolve_via_mast(mission: str, mission_ids: list[int],
                     log: logging.Logger) -> dict[int, int | None]:
    """
    Return {mission_id: tic_id} for TIC/KIC/EPIC targets.
    TIC targets resolve to themselves.

    EPIC note: MAST TIC has no EPIC filter column, so we query by the
    'ktwo{:09d}' target name one at a time. Slow for large samples (>~500);
    consider a CasJobs 2MASS bridge if needed.
    """
    if mission == "TIC":
        return {mid: mid for mid in mission_ids}

    if mission == "KIC":
        result: dict[int, int | None] = {}
        n_batches = -(-len(mission_ids) // MAST_BATCH)
        for i, chunk in enumerate(_chunks(mission_ids, MAST_BATCH)):
            log.info(f"  MAST KIC batch {i+1}/{n_batches} ({len(chunk)} IDs)...")
            try:
                t = Catalogs.query_criteria(catalog="Tic", KIC=chunk)
                if t is None or len(t) == 0:
                    continue
                for row in t:
                    try:
                        mid = int(row["KIC"])
                        tic = int(row["ID"])
                        if mid in result and result[mid] != tic:
                            log.warning(
                                f"CONFLICT: KIC_{mid} matches multiple TIC IDs "
                                f"({result[mid]}, {tic}) — skipping"
                            )
                            result[mid] = None
                        else:
                            result[mid] = tic
                    except (ValueError, TypeError):
                        continue
            except Exception as exc:
                log.error(f"  MAST KIC batch {i+1} failed: {exc}")
        return result

    if mission == "EPIC":
        log.info(f"  MAST EPIC: querying {len(mission_ids)} IDs by target name (slow)...")
        result = {}
        for mid in mission_ids:
            target_name = f"ktwo{mid:09d}"
            try:
                t = Catalogs.query_object(target_name, catalog="TIC", radius=0.0003)
                if t is None or len(t) == 0:
                    log.warning(f"UNRESOLVED: EPIC_{mid} — no TIC match for {target_name}")
                    result[mid] = None
                else:
                    result[mid] = int(t["ID"][0])
            except Exception as exc:
                log.error(f"  MAST EPIC query failed for {target_name}: {exc}")
                result[mid] = None
        return result

    return {}


# ---------------------------------------------------------------------------
# SIMBAD fallback
# ---------------------------------------------------------------------------

def resolve_via_simbad(catalog_ids: list[str],
                       log: logging.Logger) -> dict[str, str]:
    simbad = Simbad()
    simbad.TIMEOUT = 60
    result = {}
    for cid in catalog_ids:
        identifier = cid.replace("_", " ", 1)
        try:
            t = simbad.query_object(identifier)
            if t is not None and len(t) > 0:
                main_id = str(t["MAIN_ID"][0]).strip()
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

def assign_acat_ids(canonical_ids: list[str | None],
                    start: int = 1) -> tuple[dict[str, str], int]:
    """
    Assign sequential ACAT IDs to unique non-None canonical IDs.
    Existing IDs already in `mapping` are preserved.
    Returns (mapping, next_counter).
    """
    mapping: dict[str, str] = {}
    counter = start
    for cid in canonical_ids:
        if cid is not None and cid not in mapping:
            mapping[cid] = ACAT_FMT.format(counter)
            counter += 1
    return mapping, counter


# ---------------------------------------------------------------------------
# Main build
# ---------------------------------------------------------------------------

def build(sources_dir: Path, db_path: Path, overrides_path: Path,
          log_path: Path, resolve: bool, force: list[str]):

    # --- logging ---
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

    json_files = sorted(sources_dir.glob("*.json"))
    if not json_files:
        log.error(f"No JSON files found in {sources_dir}/")
        return

    overrides = load_overrides(overrides_path)
    if overrides:
        log.info(f"Loaded {len(overrides)} override(s) from {overrides_path}")

    # --- open (or create) DB and load cache ---
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SOURCES_SCHEMA)
    conn.executescript(TARGETS_SCHEMA)

    cache = load_cache(conn)  # {source: json_hash}
    force_set = {s.strip() for s in force}

    # --- classify each JSON as cached or new ---
    cached_sources = []   # (source, json_hash, rows_from_db)
    new_json_files = []   # Path objects to process fresh

    for jf in json_files:
        with open(jf) as f:
            data = json.load(f)
        source    = data["source"]
        file_hash = md5(jf)
        cached    = cache.get(source)

        if source in force_set:
            log.info(f"  {jf.name:40s}  FORCED re-process  ({source})")
            new_json_files.append(jf)
        elif cached and cached == file_hash:
            existing = load_cached_rows(conn, source)
            log.info(f"  {jf.name:40s}  CACHED  {len(existing):>6d} rows  ({source})")
            cached_sources.append((source, file_hash, existing))
        else:
            reason = "hash changed" if cached else "new source"
            log.info(f"  {jf.name:40s}  {reason}  ({source})")
            new_json_files.append(jf)

    # --- load new JSON rows ---
    new_rows   = []   # (catalog_id, mission, mission_id, source, numax, e_numax, teff, e_teff)
    by_mission = {}   # {mission: set(mission_ids)}  — only for NEW sources

    for jf in new_json_files:
        with open(jf) as f:
            data = json.load(f)
        source  = data["source"]
        mission = normalise_mission(data["mission"])
        by_mission.setdefault(mission, set())
        for t in data["targets"]:
            mid = int(t["mission_id"])
            by_mission[mission].add(mid)
            new_rows.append((
                f"{mission}_{mid}", mission, mission_to_instrument(mission), mid, source,
                t.get("numax"), t.get("e_numax"),
                t.get("teff"),  t.get("e_teff"),
            ))

    log.info(
        f"Sources: {len(cached_sources)} cached, {len(new_json_files)} to resolve"
    )

    # --- resolve new rows ---
    canonical_map: dict[str, str | None] = {}

    if new_rows and resolve:
        for mission, ids in by_mission.items():
            if mission in ("TIC", "KIC", "EPIC"):
                log.info(f"Resolving {len(ids)} {mission} IDs via MAST...")
                mast_result = resolve_via_mast(mission, list(ids), log)
                for mid, tic_id in mast_result.items():
                    cid = f"{mission}_{mid}"
                    canonical_map[cid] = f"TIC_{tic_id}" if tic_id is not None else None

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

        for cid, override_canonical in overrides.items():
            if cid in canonical_map and canonical_map[cid] != override_canonical:
                log.info(f"OVERRIDE: {cid}  {canonical_map[cid]} → {override_canonical}")
            canonical_map[cid] = override_canonical

    elif new_rows:
        log.info("Skipping ID resolution (--no-resolve)")
        for row in new_rows:
            canonical_map[row[0]] = row[0]

    # --- assign ACAT IDs ---
    # Seed the counter past whatever the DB already has, so cached ACAT IDs
    # aren't reused for new stars.
    existing_max = conn.execute(
        "SELECT MAX(CAST(SUBSTR(acat_id, 5) AS INTEGER)) FROM targets WHERE acat_id IS NOT NULL"
    ).fetchone()[0] or 0

    acat_map, _ = assign_acat_ids(list(canonical_map.values()), start=existing_max + 1)

    # --- rebuild targets table ---
    conn.executescript("DROP TABLE IF EXISTS targets;")
    conn.executescript(TARGETS_SCHEMA)

    # Re-insert cached rows verbatim
    cached_rows_all = []
    for _, _, rows in cached_sources:
        cached_rows_all.extend(rows)

    conn.executemany(
        "INSERT INTO targets (acat_id, catalog_id, mission, instrument, mission_id, source, "
        "numax, e_numax, teff, e_teff) VALUES (?,?,?,?,?,?,?,?,?,?)",
        cached_rows_all,
    )

    # Insert newly resolved rows
    new_db_rows = []
    for (catalog_id, mission, instr, mission_id, source,
         numax, e_numax, teff, e_teff) in new_rows:
        canonical = canonical_map.get(catalog_id)
        acat_id   = acat_map.get(canonical) if canonical else None
        new_db_rows.append((
            acat_id, catalog_id, mission, mission_to_instrument(mission), mission_id, source,
            numax, e_numax, teff, e_teff,
        ))

    conn.executemany(
        "INSERT INTO targets (acat_id, catalog_id, mission, instrument, mission_id, source, "
        "numax, e_numax, teff, e_teff) VALUES (?,?,?,?,?,?,?,?,?,?)",
        new_db_rows,
    )

    # Update source_cache for newly processed sources
    for jf in new_json_files:
        with open(jf) as f:
            data = json.load(f)
        update_cache(conn, data["source"], md5(jf))

    conn.commit()
    conn.close()

    total = len(cached_rows_all) + len(new_db_rows)
    log.info(f"Written {db_path}  ({total} rows total, {len(new_db_rows)} new)")
    log.info(f"Build log: {log_path}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Build the AsteroCat SQLite database.")
    p.add_argument("--sources-dir", default="sources",       type=Path)
    p.add_argument("--db",          default="catalog.db",    type=Path)
    p.add_argument("--overrides",   default="overrides.csv", type=Path)
    p.add_argument("--log",         default="build.log",     type=Path)
    p.add_argument("--no-resolve",  action="store_true",
                   help="Skip MAST/SIMBAD resolution (useful for offline testing)")
    p.add_argument("--force", nargs="*", default=[],
                   metavar="SOURCE",
                   help="Force re-resolution for named source(s) even if cached "
                        "(e.g. --force 'Lund+2024' 'Hatt+2023')")
    args = p.parse_args()
    build(args.sources_dir, args.db, args.overrides, args.log,
          not args.no_resolve, args.force)
