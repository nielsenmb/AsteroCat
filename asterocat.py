"""
app.py
------
Local Flask server for the asteroseismic catalog browser.

Usage:
    python app.py [--db catalog.db] [--port 5000]

Opens a browser tab automatically on startup.
"""

import argparse
import sqlite3
import threading
import webbrowser
from pathlib import Path

from flask import Flask, g, jsonify, request, send_from_directory

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
DEFAULT_DB   = Path(__file__).parent / "catalog.db"
STATIC_DIR   = Path(__file__).parent / "static"

app = Flask(__name__, static_folder=str(STATIC_DIR))
app.config["DB_PATH"] = str(DEFAULT_DB)


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
        "SELECT source, mission, COUNT(*) as n FROM targets GROUP BY source, mission ORDER BY source"
    ).fetchall()
    return jsonify([dict(r) for r in rows])


@app.get("/api/search")
def api_search():
    """
    Query parameters (all optional):
        q          -- free-text search on catalog_id / mission_id (substring)
        source     -- comma-separated list of source names to include
        numax_min  -- float
        numax_max  -- float
        teff_min   -- float
        teff_max   -- float
        limit      -- int (default 200)
        offset     -- int (default 0)
    """
    db = get_db()

    q          = request.args.get("q", "").strip()
    sources    = [s.strip() for s in request.args.get("source", "").split(",") if s.strip()]
    numax_min  = request.args.get("numax_min",  type=float)
    numax_max  = request.args.get("numax_max",  type=float)
    teff_min   = request.args.get("teff_min",   type=float)
    teff_max   = request.args.get("teff_max",   type=float)
    limit      = min(request.args.get("limit",  default=200, type=int), 1000)
    offset     = request.args.get("offset", default=0, type=int)

    clauses, params = [], []

    if q:
        clauses.append("(catalog_id LIKE ? OR CAST(mission_id AS TEXT) LIKE ?)")
        params += [f"%{q}%", f"%{q}%"]
    if sources:
        placeholders = ",".join("?" * len(sources))
        clauses.append(f"source IN ({placeholders})")
        params += sources
    if numax_min is not None:
        clauses.append("numax >= ?"); params.append(numax_min)
    if numax_max is not None:
        clauses.append("numax <= ?"); params.append(numax_max)
    if teff_min is not None:
        clauses.append("teff >= ?");  params.append(teff_min)
    if teff_max is not None:
        clauses.append("teff <= ?");  params.append(teff_max)

    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""

    count_row = db.execute(f"SELECT COUNT(*) FROM targets {where}", params).fetchone()
    total = count_row[0]

    rows = db.execute(
        f"SELECT catalog_id, resolved_id, mission, mission_id, source, "
        f"       numax, e_numax, teff, e_teff "
        f"FROM targets {where} "
        f"ORDER BY catalog_id, source "
        f"LIMIT ? OFFSET ?",
        params + [limit, offset],
    ).fetchall()

    return jsonify({"total": total, "limit": limit, "offset": offset,
                    "results": [dict(r) for r in rows]})


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def open_browser(port):
    webbrowser.open_new_tab(f"http://localhost:{port}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--db",   default=str(DEFAULT_DB))
    parser.add_argument("--port", default=5000, type=int)
    args = parser.parse_args()

    app.config["DB_PATH"] = args.db
    threading.Timer(1.0, open_browser, args=[args.port]).start()
    print(f"Serving catalog from {args.db}")
    print(f"Opening http://localhost:{args.port} ...")
    app.run(port=args.port, debug=False)
