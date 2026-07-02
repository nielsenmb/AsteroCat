"""
build_db.py
-----------
Scans `sources/` for canonical JSON files, resolves catalog IDs to ACAT IDs,
and builds catalog.db.

JSON schema per source file:
{
    "source":       "Hatt+2023",
    "instrument":   "TESS",
    "catalog":      "TIC",          # ID system: TIC, KIC, EPIC, HD, HR, Bayer, ...
    "ads_url":      "https://...",  # optional
    "teff_ads_url": "https://...",  # optional
    "targets": [
        {"catalog_id": 12345678, "numax": 123.4, "e_numax": 1.2,
                                  "teff": 5000.0, "e_teff": 80.0},
        ...
    ]
}

Resolution order:
  1. Cache        -- sources whose JSON hash matches the DB are skipped
  2. overrides.csv -- manual corrections always win
  3. MAST         -- TIC/KIC/EPIC → canonical TIC_<id>
  4. SIMBAD       -- everything else (HD, HR, Bayer, HIP, ...)
  5. Unresolved   -- acat_id left NULL, logged to build.log

Run:
    python scripts/build_db.py [--sources-dir sources] [--db catalog.db]
                               [--overrides overrides.csv] [--log build.log]
                               [--no-resolve] [--overwrite [SOURCE ...]]
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
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    acat_id      TEXT,
    catalog_id   TEXT NOT NULL,     -- e.g. "TIC_12345678", "HD_12345", "Bayer_alfCenA"
    catalog      TEXT NOT NULL,     -- ID system: "TIC", "KIC", "HD", "Bayer", ...
    instrument   TEXT NOT NULL,     -- e.g. "TESS", "Kepler", "HARPS@ESO"
    source       TEXT NOT NULL,     -- publication: "Hatt+2023"
    ads_url      TEXT,
    teff_ads_url TEXT,
    numax        REAL,
    e_numax      REAL,
    teff         REAL,
    e_teff       REAL
);
CREATE INDEX IF NOT EXISTS idx_acat_id    ON targets(acat_id);
CREATE INDEX IF NOT EXISTS idx_catalog_id ON targets(catalog_id);
CREATE INDEX IF NOT EXISTS idx_catalog    ON targets(catalog);
CREATE INDEX IF NOT EXISTS idx_source     ON targets(source);
CREATE INDEX IF NOT EXISTS idx_numax      ON targets(numax);
CREATE INDEX IF NOT EXISTS idx_teff       ON targets(teff);
"""

ALIASES_SCHEMA = """
CREATE TABLE IF NOT EXISTS aliases (
    alias    TEXT PRIMARY KEY,   -- "HD 12345", "alf Cen A", "TIC_9876543"
    acat_id  TEXT NOT NULL,
    origin   TEXT NOT NULL       -- "SIMBAD", "catalog_id"
);
CREATE INDEX IF NOT EXISTS idx_alias_acat ON aliases(acat_id);
"""

SOURCES_SCHEMA = """
CREATE TABLE IF NOT EXISTS source_cache (
    source     TEXT PRIMARY KEY,
    json_hash  TEXT NOT NULL,
    date_added TEXT NOT NULL
);
"""

MAST_BATCH = 1000
ACAT_FMT   = "ACAT{:09d}"

# Catalogs resolved via MAST TIC crossmatch
MAST_CATALOGS = {"TIC", "KIC", "EPIC"}

# Catalog aliases in JSON (normalise to canonical form)
CATALOG_ALIASES = {
    "tic": "TIC", "tess": "TIC",
    "kic": "KIC", "kplr": "KIC",
    "epic": "EPIC",
    "hd": "HD", "hip": "HIP", "hr": "HR",
    "bayer": "Bayer",
}

def normalise_catalog(raw: str) -> str:
    return CATALOG_ALIASES.get(raw.lower(), raw.upper())

def make_catalog_id(catalog: str, raw_id) -> str:
    """Build the catalog_id string, e.g. 'TIC_12345' or 'Bayer_alfCenA'."""
    return f"{catalog}_{raw_id}"

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
    try:
        rows = conn.execute("SELECT source, json_hash FROM source_cache").fetchall()
        return {r[0]: r[1] for r in rows}
    except sqlite3.OperationalError:
        return {}

def load_cached_rows(conn: sqlite3.Connection, source: str) -> list[tuple]:
    rows = conn.execute(
        "SELECT acat_id, catalog_id, catalog, instrument, source, "
        "       ads_url, teff_ads_url, numax, e_numax, teff, e_teff "
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
# MAST TIC crossmatch  (TIC/KIC/EPIC → canonical TIC_<id>)
# ---------------------------------------------------------------------------

def _chunks(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i : i + n]

def resolve_via_mast(catalog: str, ids: list,
                     log: logging.Logger) -> dict[str, str | None]:
    """Return {catalog_id: canonical_TIC_id_str} e.g. {'KIC_1234': 'TIC_5678'}."""
    result: dict[str, str | None] = {}

    if catalog == "TIC":
        for i in ids:
            result[make_catalog_id("TIC", i)] = make_catalog_id("TIC", i)
        return result

    if catalog == "KIC":
        int_ids = [int(i) for i in ids]
        n_batches = -(-len(int_ids) // MAST_BATCH)
        for b, chunk in enumerate(_chunks(int_ids, MAST_BATCH)):
            log.info(f"  MAST KIC batch {b+1}/{n_batches} ({len(chunk)} IDs)...")
            try:
                t = Catalogs.query_criteria(catalog="Tic", KIC=chunk)
                if t is None or len(t) == 0:
                    continue
                for row in t:
                    cid = make_catalog_id("KIC", int(row["KIC"]))
                    tic = make_catalog_id("TIC", int(row["ID"]))
                    if cid in result and result[cid] != tic:
                        log.warning(f"CONFLICT: {cid} matches multiple TIC IDs — skipping")
                        result[cid] = None
                    else:
                        result[cid] = tic
            except Exception as exc:
                log.error(f"  MAST KIC batch {b+1} failed: {exc}")
        return result

    if catalog == "EPIC":
        log.info(f"  MAST EPIC: querying {len(ids)} IDs by target name (slow)...")
        for i in ids:
            cid = make_catalog_id("EPIC", i)
            target_name = f"ktwo{int(i):09d}"
            try:
                t = Catalogs.query_object(target_name, catalog="TIC", radius=0.0003)
                if t is None or len(t) == 0:
                    log.warning(f"UNRESOLVED: {cid} — no TIC match for {target_name}")
                    result[cid] = None
                else:
                    result[cid] = make_catalog_id("TIC", int(t["ID"][0]))
            except Exception as exc:
                log.error(f"  MAST EPIC query failed for {target_name}: {exc}")
                result[cid] = None
        return result

    return {}

# ---------------------------------------------------------------------------
# SIMBAD fallback + alias harvesting
# ---------------------------------------------------------------------------

def resolve_via_simbad(catalog_ids: list[str],
                       log: logging.Logger) -> dict[str, tuple[str | None, list[str]]]:
    """
    Return {catalog_id: (canonical_id, [aliases])} where aliases are all
    SIMBAD identifiers for that object — used to populate the aliases table.
    """
    simbad = Simbad()
    simbad.add_votable_fields("ids")
    simbad.TIMEOUT = 60
    result = {}

    for cid in catalog_ids:
        identifier = cid.replace("_", " ", 1)
        try:
            t = simbad.query_object(identifier)
            if t is None or len(t) == 0:
                log.warning(f"SIMBAD: no match for {identifier}")
                result[cid] = (None, [])
                continue
            main_id = str(t["MAIN_ID"][0]).strip()
            parts   = main_id.split()
            canonical = f"{parts[0]}_{parts[-1]}" if len(parts) >= 2 else main_id
            # Harvest all aliases from the ids field
            raw_ids = str(t["IDS"][0]).split("|") if "IDS" in t.colnames else []
            aliases = [a.strip() for a in raw_ids if a.strip()]
            result[cid] = (canonical, aliases)
        except Exception as exc:
            log.error(f"SIMBAD query failed for {identifier}: {exc}")
            result[cid] = (None, [])

    return result

# ---------------------------------------------------------------------------
# ACAT ID assignment
# ---------------------------------------------------------------------------

def assign_acat_ids(canonical_ids: list[str | None],
                    existing_map: dict[str, str],
                    start: int = 1) -> tuple[dict[str, str], int]:
    mapping = dict(existing_map)
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
          log_path: Path, resolve: bool, overwrite: list[str] | None):

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

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SOURCES_SCHEMA)
    conn.executescript(TARGETS_SCHEMA)
    conn.executescript(ALIASES_SCHEMA)

    cache = load_cache(conn)
    overwrite_all = overwrite is not None and len(overwrite) == 0
    overwrite_set = {s.strip() for s in overwrite} if overwrite else set()

    # --- classify sources ---
    cached_sources = []
    new_json_files = []

    for jf in json_files:
        with open(jf) as f:
            data = json.load(f)
        source    = data["source"]
        file_hash = md5(jf)
        cached    = cache.get(source)

        if overwrite_all or source in overwrite_set:
            log.info(f"  {jf.name:40s}  OVERWRITE  ({source})")
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
    # new_rows: (catalog_id, catalog, instrument, source, ads_url, teff_ads_url,
    #            numax, e_numax, teff, e_teff)
    new_rows   = []
    by_catalog = {}   # {catalog: [catalog_id_str, ...]}

    for jf in new_json_files:
        with open(jf) as f:
            data = json.load(f)
        source     = data["source"]
        # Support old schema ("mission") alongside new ("catalog")
        raw_catalog = data.get("catalog") or data.get("mission", "")
        catalog     = normalise_catalog(raw_catalog)
        instrument  = data.get("instrument") or data.get("mission", "")
        if not data.get("instrument") and data.get("mission"):
            # Derive instrument from old-style mission key
            instrument = {"TIC": "TESS", "KIC": "Kepler", "EPIC": "K2"}.get(catalog, catalog)
        ads_url      = data.get("ads_url")
        teff_ads_url = data.get("teff_ads_url")

        by_catalog.setdefault(catalog, [])
        for t in data["targets"]:
            raw_id     = t.get("catalog_id") or t.get("mission_id", "")
            catalog_id = make_catalog_id(catalog, raw_id)
            by_catalog[catalog].append(raw_id)
            new_rows.append((
                catalog_id, catalog, instrument, source,
                ads_url, teff_ads_url,
                t.get("numax"), t.get("e_numax"),
                t.get("teff"),  t.get("e_teff"),
            ))

    log.info(f"Sources: {len(cached_sources)} cached, {len(new_json_files)} to resolve")

    # --- resolve ---
    canonical_map: dict[str, str | None] = {}
    simbad_aliases: dict[str, list[str]] = {}   # catalog_id → [simbad alias strings]

    if new_rows and resolve:
        for catalog, ids in by_catalog.items():
            if catalog in MAST_CATALOGS:
                log.info(f"Resolving {len(ids)} {catalog} IDs via MAST...")
                mast_result = resolve_via_mast(catalog, ids, log)
                canonical_map.update(mast_result)
            else:
                catalog_ids = [make_catalog_id(catalog, i) for i in ids]
                log.info(f"Resolving {len(catalog_ids)} {catalog} IDs via SIMBAD...")
                simbad_result = resolve_via_simbad(catalog_ids, log)
                for cid, (canonical, aliases) in simbad_result.items():
                    canonical_map[cid] = canonical
                    if aliases:
                        simbad_aliases[cid] = aliases
                for cid in catalog_ids:
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

    # --- pre-populate acat_map from existing DB ---
    existing_rows = conn.execute(
        "SELECT acat_id, catalog_id FROM targets WHERE acat_id IS NOT NULL"
    ).fetchall()

    acat_map: dict[str, str] = {}
    for row in existing_rows:
        acat_id, catalog_id = row
        canonical = canonical_map.get(catalog_id, catalog_id)
        if canonical and canonical not in acat_map:
            acat_map[canonical] = acat_id

    existing_max = conn.execute(
        "SELECT MAX(CAST(SUBSTR(acat_id, 5) AS INTEGER)) FROM targets WHERE acat_id IS NOT NULL"
    ).fetchone()[0] or 0

    counter = existing_max + 1
    for canonical in canonical_map.values():
        if canonical is not None and canonical not in acat_map:
            acat_map[canonical] = ACAT_FMT.format(counter)
            counter += 1

    log.info(f"Assigned {counter - existing_max - 1} new ACAT IDs ({len(acat_map)} total)")

    # --- rebuild targets and aliases tables ---
    conn.executescript("DROP TABLE IF EXISTS targets;")
    conn.executescript("DROP TABLE IF EXISTS aliases;")
    conn.executescript(TARGETS_SCHEMA)
    conn.executescript(ALIASES_SCHEMA)

    # Re-insert cached rows
    cached_rows_all = []
    for _, _, rows in cached_sources:
        cached_rows_all.extend(rows)

    conn.executemany(
        "INSERT INTO targets (acat_id, catalog_id, catalog, instrument, source, "
        "ads_url, teff_ads_url, numax, e_numax, teff, e_teff) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        [r[:11] for r in cached_rows_all],  # trim to 11 cols in case of schema migration
    )

    # Insert new rows
    new_db_rows = []
    for (catalog_id, catalog, instrument, source,
         ads_url, teff_ads_url, numax, e_numax, teff, e_teff) in new_rows:
        canonical = canonical_map.get(catalog_id)
        acat_id   = acat_map.get(canonical) if canonical else None
        new_db_rows.append((
            acat_id, catalog_id, catalog, instrument, source,
            ads_url, teff_ads_url, numax, e_numax, teff, e_teff,
        ))

    conn.executemany(
        "INSERT INTO targets (acat_id, catalog_id, catalog, instrument, source, "
        "ads_url, teff_ads_url, numax, e_numax, teff, e_teff) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        new_db_rows,
    )

    # Build aliases table: catalog_id → acat_id (for all rows)
    all_catalog_ids = conn.execute(
        "SELECT DISTINCT catalog_id, acat_id FROM targets WHERE acat_id IS NOT NULL"
    ).fetchall()

    alias_rows = []
    for catalog_id, acat_id in all_catalog_ids:
        alias_rows.append((catalog_id, acat_id, "catalog_id"))
        # Add SIMBAD aliases for ground-based targets
        for simbad_alias in simbad_aliases.get(catalog_id, []):
            alias_rows.append((simbad_alias, acat_id, "SIMBAD"))

    conn.executemany(
        "INSERT OR IGNORE INTO aliases (alias, acat_id, origin) VALUES (?,?,?)",
        alias_rows,
    )

    for jf in new_json_files:
        with open(jf) as f:
            data = json.load(f)
        update_cache(conn, data["source"], md5(jf))

    conn.commit()
    conn.close()

    total = len(cached_rows_all) + len(new_db_rows)
    log.info(f"Written {db_path}  ({total} rows, {len(alias_rows)} aliases)")
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
    p.add_argument("--overwrite", nargs="*", default=None, metavar="SOURCE",
                   help="Ignore cache and re-resolve. No args = overwrite all; "
                        "named sources = overwrite only those")
    args = p.parse_args()
    build(args.sources_dir, args.db, args.overrides, args.log,
          not args.no_resolve, args.overwrite)
