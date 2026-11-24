# Running the new database interface

This branch reads the six-table `aarchive` MySQL schema. The Flask application runs
on your computer and serves the browser at `http://localhost:5000`. Both local and
remote databases use the same read-only query implementation.

## Install

```bash
git switch new-database-layout
python -m pip install -e .
```

The legacy compilation scripts remain available, but their SQLite `catalog.db`
is not an input to this branch's browser.

## Load your SQL dump locally

Use an isolated MySQL 8 database. On Ubuntu, install and start the local server
if needed:

```bash
sudo apt install mysql-server
sudo systemctl start mysql
```

Create a fresh database using Ubuntu's administrative socket login:

```bash
sudo mysql -e 'CREATE DATABASE aarchive CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;'
gunzip -c /path/to/aarchive.sql.gz | sudo mysql --default-character-set=utf8mb4 aarchive
```

Use a new database name if `aarchive` already contains work you want to preserve.
If your administrator account uses a password, use `mysql -u root -p` instead
of `sudo mysql`. The supplied phpMyAdmin dump has table definitions and data but does not create
the database itself. Importing requires write privileges; ordinary browser use
only requires SELECT.

In an administrative MySQL session (`sudo mysql` on Ubuntu), create a separate
application account. Choose
your own password in place of the example placeholder:

```sql
CREATE USER 'asterocat'@'127.0.0.1' IDENTIFIED BY 'choose-a-local-password';
GRANT SELECT ON aarchive.* TO 'asterocat'@'127.0.0.1';
```

Set the application password without placing it directly in shell history:

```bash
read -rs -p 'Database password: ' ASTEROCAT_MYSQL_PASSWORD
export ASTEROCAT_MYSQL_PASSWORD
asterocat --mysql-host 127.0.0.1 --mysql-user asterocat --database aarchive
```

The default database port is 3306. Use `--mysql-port` if your local server uses
another port. `--port` controls the Flask browser port; `--no-browser` suppresses
opening a browser tab automatically.

## Connection settings

| Environment variable | Default |
| --- | --- |
| `ASTEROCAT_MYSQL_HOST` | `127.0.0.1` |
| `ASTEROCAT_MYSQL_PORT` | `3306` |
| `ASTEROCAT_MYSQL_USER` | `asterocat` |
| `ASTEROCAT_MYSQL_PASSWORD` | Empty |
| `ASTEROCAT_MYSQL_DATABASE` | `aarchive` |
| `ASTEROCAT_MYSQL_SSL_CA` | Unset; provide the trusted CA file for verified TLS |

The corresponding host, port, user and database CLI options override environment
settings. Passwords stay on the Flask side and are never sent to the browser.
Every application connection also sets its transactions to read-only.

When remote access returns, use the host's supported MySQL connection or tunnel
and read-only account. Configure `ASTEROCAT_MYSQL_SSL_CA` for a direct TLS
connection; this enables certificate and hostname verification. phpMyAdmin is an
administration interface; its URL is not a MySQL connection endpoint. Remote
connectivity and performance must still be checked against the live server.

## Search and data conventions

- Names and catalogue identifiers resolve through `cids`; exact variants such as
  `KIC123`, `KIC_123` and `KIC 123` are tried before a literal substring match.
  SIMBAD is an optional fallback for identifiers absent from the local catalogue.
- Each result is one `(CID, bibcode, pipeline)` measurement set. Both numax and dnu
  filters must match within that same set. Incomplete sets remain visible when
  no filter requires the absent observable.
- Publications can be selected independently of target and range filters.
  Deselecting every publication returns no results.
- Uploaded text lists use the same filters and pagination. Empty matches remain
  empty, and aliases for the same star do not duplicate its measurement sets.
- Frequency quantities and uncertainties use `uHz`. Original `nHz` values are
  divided by 1000. `-1` remains `-1` during conversion.
- The API and CSV retain missing numeric properties as `-1`; tables show a dash.
  Filters, plots and weighted summaries exclude these sentinels. Signed mode
  orders are preserved.
- Teff and its uncertainty are `-1` placeholders. Temperature controls and plot
  options are disabled. Observing-instrument functionality is omitted.
- Publication and pipeline references are separate, even if their bibcodes match.
  Empty pipeline fields stay unknown.
- Target details include all seismic observables and individual modes. The
  **Amplitude** column preserves source values. Its original unit metadata is
  retained in the detail API; reconciling amplitude definitions is deferred.
- Weighted numax/dnu summaries remain indicative only. They exclude missing values
  and use 10% of the value when a positive uncertainty is unavailable.
- Table, detail, selected export, full export and plotting share measurement-set
  identity. Plot foreground records are fetched in pages without a silent cap.

The initial implementation queries the existing tables with ordinary SELECTs.
No hosted database schema changes or materialized views are required. Export
streaming bounds application memory; broad plots can still contain many points.

## Tests

```bash
python -m pip install -e '.[test]'
python -m pytest -q
```

To enable the MySQL integration tests, select a separate local test server and an
account allowed to create and drop temporary test schemas:

```bash
export ASTEROCAT_TEST_MYSQL_PORT=3306
export ASTEROCAT_TEST_MYSQL_USER=root
read -rs -p 'Test database password: ' ASTEROCAT_TEST_MYSQL_PASSWORD
export ASTEROCAT_TEST_MYSQL_PASSWORD
python -m pytest -q
```

Integration tests only connect to loopback. They create a uniquely named
`asterocat_test_*` database and remove that database after the tests. They do not
modify `aarchive`. Without the test-server variable, those tests are skipped.

For DOM interaction tests against Flask and MySQL, install the optional Node
test dependencies (Node 20.19+ or 22.12+):

```bash
npm ci
ASTEROCAT_TEST_UI=1 python -m pytest -q
```

Keep the MySQL test-server variables set for this command. The JavaScript checks
exercise the actual application and API, including plot selection and downloads,
without requiring a graphical browser. To run the separate Chromium check:

```bash
python -m pip install playwright
python -m playwright install chromium
ASTEROCAT_TEST_BROWSER=1 python -m pytest -q tests/test_browser.py
```

The browser check uses system Chromium when available, otherwise Playwright's
installed Chromium. Plotting loads D3 from its existing CDN and requires internet
access; DOM tests use the local D3 test dependency.

## Local verification of this implementation

Tested against MySQL 8.0.44, including the supplied partial dump (2,695,398 data
rows; 282,580 distinct measurement sets), using a SELECT-only runtime account.
The automated run passed 36 tests, including MySQL and DOM interaction checks.
The opt-in Chromium test could not run in the development environment because
Unix sockets were restricted; rendered-browser verification remains outstanding.

Representative local timings after query optimization were approximately 0.28 s
for numax 100–200 uHz plus dnu 10–20 uHz (8,504 matching sets), 0.007 s for one
known CID (three sets), and 6.4 s for an unfiltered page. These are development
machine measurements, not remote-server guarantees. Remote connectivity is still
pending the server becoming available.
