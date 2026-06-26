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
        "SELECT source, mission, COUNT(*) as n "
        "FROM targets GROUP BY source, mission ORDER BY source"
    ).fetchall()
    return jsonify([dict(r) for r in rows])


@app.get("/api/search")
def api_search():
    """
    Query parameters (all optional):
        q          -- substring match on catalog_id or mission_id
        source     -- comma-separated source names to include
        numax_min  -- float
        numax_max  -- float
        teff_min   -- float
        teff_max   -- float
        limit      -- int (default 200, max 1000)
        offset     -- int (default 0)
    """
    db = get_db()

    q         = request.args.get("q", "").strip()
    sources   = [s.strip() for s in request.args.get("source", "").split(",") if s.strip()]
    numax_min = request.args.get("numax_min", type=float)
    numax_max = request.args.get("numax_max", type=float)
    teff_min  = request.args.get("teff_min",  type=float)
    teff_max  = request.args.get("teff_max",  type=float)
    limit     = min(request.args.get("limit",  default=200, type=int), 1000)
    offset    = request.args.get("offset", default=0, type=int)

    clauses, params = [], []

    if q:
        clauses.append("(catalog_id LIKE ? OR CAST(mission_id AS TEXT) LIKE ?)")
        params += [f"%{q}%", f"%{q}%"]
    if sources:
        placeholders = ",".join("?" * len(sources))
        clauses.append(f"source IN ({placeholders})")
        params += sources
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
        f"SELECT catalog_id, resolved_id, mission, mission_id, source,"
        f"       numax, e_numax, teff, e_teff "
        f"FROM targets {where} "
        f"ORDER BY catalog_id, source "
        f"LIMIT ? OFFSET ?",
        params + [limit, offset],
    ).fetchall()

    return jsonify({"total": total, "limit": limit, "offset": offset,
                    "results": [dict(r) for r in rows]})


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
