"""Read-only access to the aarchive MySQL schema."""

import math
import re

import pymysql


TABLES = ("p", "g", "mixed", "rotmag")
SORT_COLUMNS = {"cid", "bibcode", "pipeline", "numax", "e_numax", "dnu", "e_dnu"}
EXPORT_COLUMNS = ["cid", "bibcode", "pipeline", "numax", "e_numax", "dnu", "e_dnu",
                  "frequency_units", "teff", "e_teff"]


def frequency(value, units):
    """Convert a frequency to uHz while preserving the missing sentinel.

    Parameters
    ----------
    value : float or None
        Frequency or uncertainty; -1 denotes missing data.
    units : str
        Source frequency unit.

    Returns
    -------
    float
        Value in uHz, or -1 for missing or unsupported data.
    """
    if value is None or value == -1:
        return -1
    factor = {"uHz": 1, "μHz": 1, "µHz": 1, "nHz": 0.001, "mHz": 1000,
              "Hz": 1e6}.get(units)
    return value * factor if factor is not None and math.isfinite(value) else -1


def frequency_sql(column, alias=""):
    """Build the SQL counterpart of frequency normalization.

    Parameters
    ----------
    column : str
        Internal, trusted column name: value or err.
    alias : str, optional
        Internal table alias for a joined measurement.

    Returns
    -------
    str
        MySQL expression preserving -1 before conversion.
    """
    prefix = f"{alias}." if alias else ""
    value, units = f"{prefix}`{column}`", f"{prefix}units"
    return (
        f"CASE WHEN {value} IS NULL OR {value} = -1 THEN -1 "
        f"WHEN BINARY {units} IN ('uHz', 'μHz', 'µHz') THEN {value} "
        f"WHEN BINARY {units} = 'nHz' THEN {value} / 1000.0 "
        f"WHEN BINARY {units} = 'mHz' THEN {value} * 1000.0 "
        f"WHEN BINARY {units} = 'Hz' THEN {value} * 1000000.0 ELSE -1 END"
    )


def parse_filters(args):
    """Validate search parameters shared by tables, plots and exports.

    Parameters
    ----------
    args : Mapping
        JSON request object or URL query parameters.

    Returns
    -------
    dict
        Validated filters; omitted source/CID lists mean unrestricted.

    Raises
    ------
    ValueError
        If a filter is malformed or requests unavailable metadata.
    """
    result = {"q": str(args.get("q", "")).strip()}
    if len(result["q"]) > 200:
        raise ValueError("Target names must be at most 200 characters.")
    for name in ("teff_min", "teff_max", "instrument"):
        if args.get(name) not in (None, ""):
            raise ValueError("Temperature and instrument filtering are unavailable.")
    for name in ("cids", "sources"):
        value = args.get(name)
        if isinstance(value, str):
            value = [x.strip() for x in value.split(",") if x.strip()]
        if value is not None:
            if not isinstance(value, list) or any(not isinstance(x, str) for x in value):
                raise ValueError(f"{name} must be a list of strings.")
            if len(value) > 2000 or any(len(x) > 200 for x in value):
                raise ValueError(f"Too many or oversized {name} entries (maximum 2000).")
            result[name] = list(dict.fromkeys(value))
    for field in ("numax", "dnu"):
        for bound in ("min", "max"):
            name = f"{field}_{bound}"
            if args.get(name) not in (None, ""):
                try:
                    value = float(args[name])
                except (TypeError, ValueError, OverflowError) as exc:
                    raise ValueError(f"{name} must be a number.") from exc
                if not math.isfinite(value):
                    raise ValueError(f"{name} must be finite.")
                result[name] = value
        if result.get(f"{field}_min", -math.inf) > result.get(f"{field}_max", math.inf):
            raise ValueError(f"{field} minimum exceeds maximum.")
    result["sort_col"] = args.get("sort_col", "cid")
    result["sort_dir"] = str(args.get("sort_dir", "asc")).lower()
    if result["sort_col"] not in SORT_COLUMNS or result["sort_dir"] not in ("asc", "desc"):
        raise ValueError("Unsupported sort column or direction.")
    return result


def connect(config):
    """Open a MySQL session whose transactions are read-only.

    Parameters
    ----------
    config : dict
        PyMySQL connection arguments, including optional verified TLS settings.

    Returns
    -------
    pymysql.Connection
        Connection owned by the current request.
    """
    connection = pymysql.connect(**config, charset="utf8mb4", autocommit=False,
                                 cursorclass=pymysql.cursors.DictCursor)
    with connection.cursor() as cursor:
        cursor.execute("SET SESSION TRANSACTION READ ONLY")
    return connection


class Archive:
    """Query aarchive without modifying its tables or creating database views."""

    def __init__(self, connection):
        """Bind an existing connection.

        Parameters
        ----------
        connection : pymysql.Connection
            Read-only connection owned by the caller.
        """
        self.connection = connection

    def rows(self, sql, params=()):
        """Fetch rows from a parameterized query.

        Parameters
        ----------
        sql : str
            SELECT statement.
        params : sequence, optional
            Bound query values.

        Returns
        -------
        list of dict
            Result rows.
        """
        with self.connection.cursor() as cursor:
            cursor.execute(sql, params)
            return list(cursor.fetchall())

    def resolve(self, name, partial=True):
        """Resolve literal names and common catalogue-number formats to CIDs.

        Parameters
        ----------
        name : str
            Name, alias or CID.
        partial : bool, optional
            Permit a literal substring match when exact variants fail.

        Returns
        -------
        list of str
            Unique matching CIDs. No match returns an empty list.
        """
        name = " ".join(name.strip().split())
        if not name:
            return []
        variants = {name}
        match = re.fullmatch(r"(TIC|KIC|EPIC|HD|HIP|HR)[ _]*(\d+)", name, re.I)
        if match:
            prefix, number = match.groups()
            variants.update(prefix.upper() + sep + number for sep in ("", " ", "_"))
        placeholders = ",".join(["%s"] * len(variants))
        rows = self.rows(f"SELECT DISTINCT CID FROM cids WHERE ID IN ({placeholders})",
                         sorted(variants))
        # A CID can be a valid search key even when it is not listed as its own alias.
        if not rows:
            rows = self.rows("SELECT DISTINCT CID FROM cids WHERE CID = %s", (name,))
        if not rows and partial:
            pattern = name.replace("!", "!!").replace("%", "!%").replace("_", "!_")
            rows = self.rows("SELECT DISTINCT CID FROM cids WHERE ID LIKE %s ESCAPE '!' "
                             "ORDER BY CID LIMIT 2001", (f"%{pattern}%",))
        cids = sorted({row["CID"] for row in rows if row["CID"]})
        if len(cids) > 2000:
            raise ValueError("Name matches too many targets; use a more specific identifier.")
        return cids

    def query(self, filters, axes=()):
        """Build a grouped query, matching all ranges within one measurement set.

        Parameters
        ----------
        filters : dict
            Validated search parameters.
        axes : sequence of str, optional
            Plot columns that must contain available values.

        Returns
        -------
        tuple
            SQL and bound parameters. The query has no ORDER BY or LIMIT.
        """
        clauses, params = [], []
        cids = filters.get("cids")
        if filters.get("q"):
            resolved = self.resolve(filters["q"])
            cids = resolved if cids is None else sorted(set(cids).intersection(resolved))
        for column, values in (("CID", cids), ("bibcode", filters.get("sources"))):
            if values is not None:
                placeholders = ",".join(["%s"] * len(values))
                clauses.append(f"{column} IN ({placeholders})" if values else "1 = 0")
                params.extend(values)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        parts = [f"SELECT CID, pipeline, bibcode, Obsname, value, err, units FROM {t}{where}"
                 for t in TABLES]
        parts.append("SELECT DISTINCT CID, pipeline, bibcode, '' AS Obsname, "
                     f"-1 AS value, -1 AS err, '' AS units FROM modes{where}")
        fields = []
        for obs, name in (("νmax", "numax"), ("Δν", "dnu")):
            for source, dest in (("value", name), ("err", f"e_{name}")):
                fields.append(f"COALESCE(MAX(CASE WHEN Obsname = '{obs}' THEN "
                              f"{frequency_sql(source)} END), -1) AS {dest}")
        grouped = ("SELECT CID AS cid, pipeline, bibcode, " + ", ".join(fields)
                   + ", -1 AS teff, -1 AS e_teff, 'uHz' AS frequency_units FROM ("
                   + " UNION ALL ".join(parts) + ") measurements GROUP BY CID, pipeline, bibcode")
        outer, bounds = [], []
        for field in ("numax", "dnu"):
            active = field in axes or any(f"{field}_{b}" in filters for b in ("min", "max"))
            if active:
                outer.append(f"{field} <> -1")
            for bound, op in (("min", ">="), ("max", "<=")):
                key = f"{field}_{bound}"
                if key in filters:
                    outer.append(f"{field} {op} %s")
                    bounds.append(filters[key])
        if outer:
            # A range or axis requires a global observable. Anchor on that p row
            # and look up its partner using the existing composite primary key.
            base_name = "numax" if "numax" in axes or any(
                f"numax_{bound}" in filters for bound in ("min", "max")) else "dnu"
            obs = {"numax": "νmax", "dnu": "Δν"}
            partner_name = "dnu" if base_name == "numax" else "numax"
            fields = []
            for name in ("numax", "dnu"):
                alias = "base" if name == base_name else "partner"
                for column, dest in (("value", name), ("err", f"e_{name}")):
                    fields.append(f"{frequency_sql(column, alias)} AS {dest}")
            # Only trusted column names are qualified; bound values stay separate.
            qualified = where.replace("CID", "base.CID").replace("bibcode", "base.bibcode")
            grouped = (
                "SELECT base.CID AS cid, base.pipeline, base.bibcode, " + ", ".join(fields)
                + ", -1 AS teff, -1 AS e_teff, 'uHz' AS frequency_units FROM p base "
                "LEFT JOIN p partner ON partner.CID = base.CID "
                "AND partner.pipeline = base.pipeline AND partner.bibcode = base.bibcode "
                f"AND partner.Obsname = '{obs[partner_name]}' "
                + (qualified + " AND " if qualified else " WHERE ")
                + f"base.Obsname = '{obs[base_name]}'"
            )
            parts = [grouped]
        sql = f"SELECT * FROM ({grouped}) result"
        if outer:
            sql += " WHERE " + " AND ".join(outer)
        return sql, params * len(parts) + bounds

    def search(self, filters, limit=200, offset=0, axes=(), random=False):
        """Return a stable page of measurement sets and the matching total.

        Parameters
        ----------
        filters : dict
            Validated search parameters.
        limit, offset : int, optional
            Pagination bounds.
        axes : sequence of str, optional
            Required plot quantities.
        random : bool, optional
            Sample the plot background using MySQL RAND().

        Returns
        -------
        dict
            Total, page bounds and result rows.
        """
        sql, params = self.query(filters, axes)
        order = "RAND()" if random else self.order(filters)
        rows = self.rows("SELECT result.*, COUNT(*) OVER () AS _total "
                         f"FROM ({sql}) result ORDER BY {order} LIMIT %s OFFSET %s",
                         params + [limit, offset])
        total = rows[0]["_total"] if rows else 0
        for row in rows:
            row.pop("_total")
        if not rows and offset:
            total = self.rows(f"SELECT COUNT(*) AS n FROM ({sql}) matches", params)[0]["n"]
        return {"total": total, "limit": limit, "offset": offset, "results": rows}

    @staticmethod
    def order(filters):
        """Return a deterministic order with a complete measurement-set tie break.

        Parameters
        ----------
        filters : dict
            Validated search parameters.

        Returns
        -------
        str
            ORDER BY expression using whitelisted columns.
        """
        column = filters.get("sort_col", "cid")
        direction = filters.get("sort_dir", "asc")
        return f"`{column}` {direction}, cid, bibcode, pipeline"

    def sources(self):
        """Count measurement sets by publication.

        Returns
        -------
        list of dict
            Publication bibcodes and measurement-set counts.
        """
        sql = " UNION ".join(f"SELECT CID, pipeline, bibcode FROM {t}" for t in (*TABLES, "modes"))
        return self.rows(f"SELECT bibcode, COUNT(*) AS n FROM ({sql}) sets "
                         "GROUP BY bibcode ORDER BY bibcode")

    def details(self, cid):
        """Read all seismic measurements and modes for one target.

        Parameters
        ----------
        cid : str
            Common target identifier.

        Returns
        -------
        dict
            Aliases, measurement sets, observables and modes with provenance.
        """
        measurements = []
        for table in TABLES:
            for row in self.rows(f"SELECT * FROM {table} WHERE CID = %s "
                                 "ORDER BY bibcode, pipeline, Obsname", (cid,)):
                row["table"] = table
                if row["units"] in ("uHz", "μHz", "µHz", "nHz", "mHz", "Hz"):
                    row["value"] = frequency(row["value"], row["units"])
                    row["err"] = frequency(row["err"], row["units"])
                    row["units"] = "uHz"
                for key in ("value", "err"):
                    if row[key] is None:
                        row[key] = -1
                measurements.append(row)
        modes = self.rows("SELECT * FROM modes WHERE CID = %s "
                          "ORDER BY bibcode, pipeline, ell, freq", (cid,))
        for row in modes:
            for field in ("freq", "Γ"):
                units = row[f"{field}_units"]
                row[field] = frequency(row[field], units)
                row[f"{field}_err"] = frequency(row[f"{field}_err"], units)
                row[f"{field}_units"] = "uHz"
            for field in ("n_p", "n_g", "A", "A_err"):
                if row[field] is None:
                    row[field] = -1
        sql, params = self.query({"cids": [cid]})
        return {"cid": cid, "aliases": [r["ID"] for r in self.rows(
                    "SELECT ID FROM cids WHERE CID = %s ORDER BY ID", (cid,))],
                "results": self.rows(sql + " ORDER BY bibcode, pipeline", params),
                "measurements": measurements, "modes": modes}

