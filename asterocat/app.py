"""Flask interface and CLI for the read-only aarchive catalogue browser."""

import argparse
import csv
import io
import logging
import os
import threading
import webbrowser
from pathlib import Path

import pymysql
from flask import Flask, g, jsonify, request, send_from_directory
from werkzeug.exceptions import HTTPException

from .database import Archive, EXPORT_COLUMNS, connect, parse_filters


STATIC_DIR = Path(__file__).parent / "static"


def mysql_config():
    """Read connection settings from the environment.

    Returns
    -------
    dict
        PyMySQL arguments. Credentials never enter browser responses.
    """
    config = {
        "host": os.environ.get("ASTEROCAT_MYSQL_HOST", "127.0.0.1"),
        "port": int(os.environ.get("ASTEROCAT_MYSQL_PORT", "3306")),
        "user": os.environ.get("ASTEROCAT_MYSQL_USER", "asterocat"),
        "password": os.environ.get("ASTEROCAT_MYSQL_PASSWORD", ""),
        "database": os.environ.get("ASTEROCAT_MYSQL_DATABASE", "aarchive"),
        "connect_timeout": 10, "read_timeout": 120, "write_timeout": 30,
    }
    if os.environ.get("ASTEROCAT_MYSQL_SSL_CA"):
        config.update(ssl_ca=os.environ["ASTEROCAT_MYSQL_SSL_CA"],
                      ssl_verify_cert=True, ssl_verify_identity=True)
    return config


def get_archive():
    """Get the archive connection for the current request.

    Returns
    -------
    Archive
        Data-access object backed by a read-only MySQL session.
    """
    from flask import current_app
    if "archive" not in g:
        g.archive = Archive(connect(current_app.config["MYSQL"]))
    return g.archive


def arguments():
    """Read a JSON object or query parameters.

    Returns
    -------
    dict or MultiDict
        Request arguments.
    """
    args = request.get_json() if request.method == "POST" else request.args
    if not isinstance(args, dict):
        raise ValueError("Request body must be a JSON object.")
    return args


def integer(args, key, default, minimum, maximum):
    """Validate an integer request parameter.

    Parameters
    ----------
    args : Mapping
        Input arguments.
    key : str
        Parameter name.
    default, minimum, maximum : int
        Default and inclusive bounds.

    Returns
    -------
    int
        Validated value.
    """
    raw = args.get(key, default)
    try:
        value = int(raw)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{key} must be an integer.") from exc
    if str(value) != str(raw) or not minimum <= value <= maximum:
        raise ValueError(f"{key} must be an integer between {minimum} and {maximum}.")
    return value


def simbad_ids(name):
    """Resolve a name through the optional live SIMBAD service.

    Parameters
    ----------
    name : str
        Target name.

    Returns
    -------
    list of str
        Identifiers returned by SIMBAD.
    """
    from astroquery.simbad import Simbad
    client = Simbad()
    client.TIMEOUT = 15
    table = client.query_objectids(name)
    if table is None:
        return []
    column = "id" if "id" in table.colnames else "ID"
    return [str(value).strip() for value in table[column] if str(value).strip()]


def create_app(config=None):
    """Create the browser application.

    Parameters
    ----------
    config : dict, optional
        Flask configuration overrides, including MYSQL connection settings.

    Returns
    -------
    Flask
        Application with search, detail, plot, resolution and export routes.
    """
    app = Flask(__name__, static_folder=str(STATIC_DIR))
    app.config.update(MYSQL=mysql_config(), MAX_CONTENT_LENGTH=1024 * 1024)
    if config:
        app.config.update(config)

    @app.teardown_appcontext
    def close_db(exc=None):
        """Close the request connection and its read transaction.

        Parameters
        ----------
        exc : Exception, optional
            Request error, if any.
        """
        archive = g.pop("archive", None)
        if archive is not None:
            archive.connection.close()

    @app.errorhandler(ValueError)
    def invalid_request(exc):
        """Return a readable validation error.

        Parameters
        ----------
        exc : ValueError
            Invalid input.

        Returns
        -------
        tuple
            JSON response and HTTP status.
        """
        return jsonify(error=str(exc)), 400

    @app.errorhandler(pymysql.MySQLError)
    def database_error(exc):
        """Report database failures without exposing connection details.

        Parameters
        ----------
        exc : pymysql.MySQLError
            Database failure.

        Returns
        -------
        tuple
            JSON response and HTTP status.
        """
        app.logger.exception("Archive query failed")
        return jsonify(error="Database unavailable or query failed. Check the server log."), 503

    @app.errorhandler(HTTPException)
    def http_error(exc):
        """Return JSON for API-level HTTP errors.

        Parameters
        ----------
        exc : HTTPException
            HTTP failure.

        Returns
        -------
        tuple
            JSON response and HTTP status.
        """
        return jsonify(error=exc.description), exc.code

    @app.get("/")
    def index():
        """Serve the browser interface.

        Returns
        -------
        Response
            HTML document.
        """
        return send_from_directory(STATIC_DIR, "index.html")

    @app.get("/api/sources")
    def sources():
        """List publication counts.

        Returns
        -------
        Response
            JSON publication list.
        """
        return jsonify(get_archive().sources())

    @app.route("/api/search", methods=["GET", "POST"])
    def search():
        """Search measurement sets with shared name and range filters.

        Returns
        -------
        Response
            Paginated JSON records.
        """
        args = arguments()
        filters = parse_filters(args)
        limit = integer(args, "limit", 200, 1, 1000)
        offset = integer(args, "offset", 0, 0, 10000000)
        return jsonify(get_archive().search(filters, limit, offset))

    @app.get("/api/target/<path:cid>")
    def target(cid):
        """Return target details including observables and individual modes.

        Parameters
        ----------
        cid : str
            Common target identifier.

        Returns
        -------
        Response
            Target detail JSON.
        """
        return jsonify(get_archive().details(cid))

    @app.post("/api/resolve")
    def resolve():
        """Resolve a target list without broadening an empty result to all stars.

        Returns
        -------
        Response
            Resolved CIDs, unmatched names and duplicate aliases.
        """
        args = arguments()
        names = args.get("names", [])
        if not isinstance(names, list) or not 1 <= len(names) <= 500:
            raise ValueError("Provide between 1 and 500 target names.")
        if any(not isinstance(n, str) or not n.strip() or len(n) > 200 for n in names):
            raise ValueError("Target names must be nonempty strings of at most 200 characters.")
        if args.get("online", False) not in (True, False):
            raise ValueError("online must be a boolean.")
        archive = get_archive()
        mapping, missing, errors = {}, [], []
        for name in dict.fromkeys(names):
            cids = archive.resolve(name)
            if not cids and args.get("online", False):
                try:
                    ids = simbad_ids(name)
                    variants = set(ids)
                    if variants:
                        placeholders = ",".join(["%s"] * len(variants))
                        found = archive.rows("SELECT DISTINCT CID FROM cids WHERE ID IN "
                                             f"({placeholders})", sorted(variants))
                        cids = [row["CID"] for row in found if row["CID"]]
                except Exception:
                    app.logger.warning("SIMBAD lookup failed", exc_info=True)
                    errors.append(name)
            if not cids:
                missing.append(name)
            for cid in cids:
                mapping.setdefault(cid, []).append(name)
        if len(mapping) > 2000:
            raise ValueError("List resolves to more than 2000 targets; split it into smaller lists.")
        return jsonify(cids=sorted(mapping), missing=missing, lookup_errors=errors,
                       duplicates={cid: ns for cid, ns in mapping.items() if len(ns) > 1})

    @app.route("/api/plot/<layer>", methods=["GET", "POST"])
    def plot(layer):
        """Return plot records with the same filters and provenance as the table.

        Parameters
        ----------
        layer : str
            Either background or foreground.

        Returns
        -------
        Response
            Paginated plot records; the foreground can be fetched in full.
        """
        args = arguments()
        axes = [args.get("x_col", "numax"), args.get("y_col", "dnu")]
        if any(axis not in ("numax", "dnu") for axis in axes):
            raise ValueError("Plot axes must be numax or dnu; Teff is unavailable.")
        if layer == "background":
            limit = integer(args, "limit", 10000, 1, 10000)
            return jsonify(get_archive().search({}, limit, axes=axes, random=True))
        if layer != "foreground":
            raise ValueError("Unknown plot layer.")
        filters = parse_filters(args)
        limit = integer(args, "limit", 10000, 1, 10000)
        offset = integer(args, "offset", 0, 0, 10000000)
        return jsonify(get_archive().search(filters, limit, offset, axes=axes))

    @app.post("/api/export")
    def export():
        """Stream every matching measurement set as quoted CSV.

        Returns
        -------
        Response
            CSV download with the same filtering and ordering as the table.
        """
        filters = parse_filters(arguments())
        archive = get_archive()
        sql, params = archive.query(filters)
        cursor = archive.connection.cursor(pymysql.cursors.SSDictCursor)
        cursor.execute(sql + " ORDER BY " + archive.order(filters), params)
        # The response outlives Flask's request teardown; it owns this connection.
        g.pop("archive")

        def close_export():
            """Release the export connection, including an unconsumed response.

            Returns
            -------
            None
                Closes the connection if it is still open.
            """
            if archive.connection.open:
                try:
                    cursor.close()
                finally:
                    archive.connection.close()

        def generate():
            """Yield CSV chunks without retaining the complete result in memory.

            Yields
            ------
            str
                Header or batches of CSV records.
            """
            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=EXPORT_COLUMNS, extrasaction="ignore")
            writer.writeheader()
            try:
                yield output.getvalue()
                while rows := cursor.fetchmany(1000):
                    output.seek(0)
                    output.truncate()
                    writer.writerows(rows)
                    yield output.getvalue()
            finally:
                close_export()

        response = app.response_class(generate(), mimetype="text/csv", headers={
            "Content-Disposition": 'attachment; filename="asterocat_results.csv"'})
        response.call_on_close(close_export)
        return response

    return app


app = create_app()


def main():
    """Launch the local browser connected to a local or remote MySQL database.

    Returns
    -------
    None
        Runs the Flask server until interrupted.
    """
    parser = argparse.ArgumentParser(description="AsteroCat aarchive browser")
    parser.add_argument("--mysql-host", default=app.config["MYSQL"]["host"])
    parser.add_argument("--mysql-port", type=int, default=app.config["MYSQL"]["port"])
    parser.add_argument("--mysql-user", default=app.config["MYSQL"]["user"])
    parser.add_argument("--database", default=app.config["MYSQL"]["database"])
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    app.config["MYSQL"].update(host=args.mysql_host, port=args.mysql_port,
                               user=args.mysql_user, database=args.database)
    logging.basicConfig(level=logging.INFO)
    if not args.no_browser:
        threading.Timer(1, webbrowser.open_new_tab,
                        args=[f"http://localhost:{args.port}"]).start()
    app.run(host="127.0.0.1", port=args.port, debug=False)


if __name__ == "__main__":
    main()
