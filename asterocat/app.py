"""
asterocat/app.py
----------------
Local Flask server for the asteroseismic catalog browser.

Installed as the `asterocat` console script via pyproject.toml.

Usage (after pip install):
    asterocat [--db PATH] [--port PORT]

Usage (dev):
    python -m asterocat.app [--db PATH] [--port PORT]
"""

import argparse
import sqlite3
import threading
import webbrowser
from pathlib import Path

import re
from flask import Flask, g, jsonify, request, send_from_directory

# Static files live next to this module inside the installed package.
STATIC_DIR = Path(__file__).parent / "static"

app = Flask(__name__, static_folder=str(STATIC_DIR))
app.config["DB_PATH"] = ""   # set at startup


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(app.config["DB_PATH"])
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/")
def index():
    return send_from_directory(STATIC_DIR, "index.html")


@app.get("/api/sources")
def api_sources():
    """Return list of loaded sources and their row counts."""
    db = get_db()
    rows = db.execute(
        "SELECT source, catalog, instrument, COUNT(*) as n "
        "FROM targets GROUP BY source, catalog, instrument ORDER BY source"
    ).fetchall()
    return jsonify([dict(r) for r in rows])


@app.get("/api/search")
def api_search():
    """
    Query parameters (all optional):
        q          -- match on catalog_id; must include mission prefix (e.g. TIC1234, KIC5678)
        source     -- comma-separated source names to include
        numax_min  -- float
        numax_max  -- float
        teff_min   -- float
        teff_max   -- float
        limit      -- int (default 200, max 1000)
        offset     -- int (default 0)
        sort_col   -- column to sort by (default: acat_id)
        sort_dir   -- 'asc' or 'desc' (default: asc)
    """
    db = get_db()

    q            = request.args.get("q", "").strip()
    sources      = [s.strip() for s in request.args.get("source", "").split(",") if s.strip()]
    instruments  = [i.strip() for i in request.args.get("instrument", "").split(",") if i.strip()]
    numax_min = request.args.get("numax_min", type=float)
    numax_max = request.args.get("numax_max", type=float)
    teff_min  = request.args.get("teff_min",  type=float)
    teff_max  = request.args.get("teff_max",  type=float)
    limit     = min(request.args.get("limit",  default=200, type=int), 1000)
    offset    = request.args.get("offset", default=0, type=int)
    sort_col  = request.args.get("sort_col", "acat_id")
    sort_dir  = request.args.get("sort_dir", "asc").lower()

    # Whitelist sortable columns to prevent SQL injection
    SORTABLE = {"acat_id", "catalog_id", "catalog", "instrument", "source",
                "numax", "e_numax", "teff", "e_teff"}
    if sort_col not in SORTABLE:
        sort_col = "acat_id"
    if sort_dir not in ("asc", "desc"):
        sort_dir = "asc"

    clauses, params = [], []

    if q:
        # Normalise input: insert _ after mission prefix if absent
        # e.g. "TIC1234" → "TIC_1234", "TIC_1234" → "TIC_1234", "1234" → reject
        q_norm = re.sub(r'^([A-Za-z]+)_?(\d+)$', r'\1_\2', q.strip())
        if re.match(r'^[A-Za-z]+_\d+', q_norm):
            clauses.append("catalog_id LIKE ?")
            params.append(f"%{q_norm}%")
    if sources:
        placeholders = ",".join("?" * len(sources))
        clauses.append(f"source IN ({placeholders})")
        params += sources
    if instruments:
        placeholders = ",".join("?" * len(instruments))
        clauses.append(f"instrument IN ({placeholders})")
        params += instruments
    if numax_min is not None:
        clauses.append("numax >= ?");  params.append(numax_min)
    if numax_max is not None:
        clauses.append("numax <= ?");  params.append(numax_max)
    if teff_min is not None:
        clauses.append("teff >= ?");   params.append(teff_min)
    if teff_max is not None:
        clauses.append("teff <= ?");   params.append(teff_max)

    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""

    total = db.execute(
        f"SELECT COUNT(*) FROM targets {where}", params
    ).fetchone()[0]

    rows = db.execute(
        f"SELECT acat_id, catalog_id, catalog, instrument, source,"
        f"       ads_url, teff_ads_url, numax, e_numax, teff, e_teff "
        f"FROM targets {where} "
        f"ORDER BY {sort_col} {sort_dir.upper()}, acat_id "
        f"LIMIT ? OFFSET ?",
        params + [limit, offset],
    ).fetchall()

    return jsonify({"total": total, "limit": limit, "offset": offset,
                    "results": [dict(r) for r in rows]})



@app.get("/api/acat/<acat_id>")
def api_acat(acat_id):
    db = get_db()
    rows = db.execute(
        "SELECT acat_id, catalog_id, catalog, instrument, source, "
        "       ads_url, teff_ads_url, numax, e_numax, teff, e_teff "
        "FROM targets WHERE acat_id = ? "
        "ORDER BY source",
        (acat_id,),
    ).fetchall()
    return jsonify([dict(r) for r in rows])



@app.get("/api/plot/background")
def api_plot_background():
    """Return up to 10k randomly sampled rows for the plot background."""
    db   = get_db()
    n    = request.args.get("n", default=10000, type=int)
    rows = db.execute(
        "SELECT acat_id, catalog_id, catalog, instrument, numax, teff "
        "FROM targets "
        "WHERE numax IS NOT NULL AND teff IS NOT NULL "
        "ORDER BY RANDOM() LIMIT ?",
        (n,),
    ).fetchall()
    return jsonify([dict(r) for r in rows])


@app.get("/api/plot/foreground")
def api_plot_foreground():
    """Return search-filtered rows for the plot foreground (same filters as /api/search)."""
    db = get_db()

    q           = request.args.get("q", "").strip()
    sources     = [s.strip() for s in request.args.get("source",     "").split(",") if s.strip()]
    instruments = [i.strip() for i in request.args.get("instrument", "").split(",") if i.strip()]
    numax_min   = request.args.get("numax_min", type=float)
    numax_max   = request.args.get("numax_max", type=float)
    teff_min    = request.args.get("teff_min",  type=float)
    teff_max    = request.args.get("teff_max",  type=float)

    clauses, params = [], []
    clauses.append("numax IS NOT NULL AND teff IS NOT NULL")

    if q:
        q_norm = re.sub(r'^([A-Za-z]+)_?(\d+)$', r'\1_\2', q.strip())
        if re.match(r'^[A-Za-z]+_\d+', q_norm):
            clauses.append("catalog_id LIKE ?")
            params.append(f"%{q_norm}%")
    if sources:
        placeholders = ",".join("?" * len(sources))
        clauses.append(f"source IN ({placeholders})")
        params += sources
    if instruments:
        placeholders = ",".join("?" * len(instruments))
        clauses.append(f"instrument IN ({placeholders})")
        params += instruments
    if numax_min is not None:
        clauses.append("numax >= ?");  params.append(numax_min)
    if numax_max is not None:
        clauses.append("numax <= ?");  params.append(numax_max)
    if teff_min is not None:
        clauses.append("teff >= ?");   params.append(teff_min)
    if teff_max is not None:
        clauses.append("teff <= ?");   params.append(teff_max)

    where = "WHERE " + " AND ".join(clauses)
    rows  = db.execute(
        f"SELECT acat_id, catalog_id, catalog, instrument, source, ads_url, teff_ads_url, numax, teff "
        f"FROM targets {where} ORDER BY acat_id",
        params,
    ).fetchall()
    return jsonify([dict(r) for r in rows])



@app.get("/api/search/alias")
def api_search_alias():
    """
    Search the aliases table for a free-text identifier (e.g. "HD 12345",
    "alf Cen A"). Returns matching acat_ids and their target rows.
    """
    db    = get_db()
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify([])

    # Try exact match first, then prefix match
    rows = db.execute(
        "SELECT t.acat_id, t.catalog_id, t.catalog, t.instrument, t.source, "
        "       t.ads_url, t.teff_ads_url, t.numax, t.e_numax, t.teff, t.e_teff, "
        "       a.alias "
        "FROM aliases a JOIN targets t ON a.acat_id = t.acat_id "
        "WHERE a.alias LIKE ? "
        "ORDER BY t.catalog_id, t.source "
        "LIMIT 200",
        (f"%{query}%",),
    ).fetchall()
    return jsonify([dict(r) for r in rows])


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        prog="asterocat",
        description="AsteroCat — asteroseismic catalog browser",
    )
    parser.add_argument(
        "--db",
        default=str(Path.cwd() / "catalog.db"),
        help="Path to catalog.db (default: ./catalog.db)",
    )
    parser.add_argument(
        "--port", default=5000, type=int,
        help="Port for the local web server (default: 5000)",
    )
    parser.add_argument(
        "--no-browser", action="store_true",
        help="Don't open a browser tab automatically",
    )
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        parser.error(
            f"Database not found: {db_path}\n"
            "Run `python scripts/build_db.py` first to build it."
        )

    app.config["DB_PATH"] = str(db_path)

    if not args.no_browser:
        threading.Timer(1.0, webbrowser.open_new_tab,
                        args=[f"http://localhost:{args.port}"]).start()

    print(f"AsteroCat  |  db: {db_path}  |  http://localhost:{args.port}")
    app.run(port=args.port, debug=False)


if __name__ == "__main__":
    main()
