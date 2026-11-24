# AsteroCat: migration to the aarchive database

Status: planning; application implementation has not started.
Branch: `new-database-layout`
Baseline: `main` at `ddd5441accb94b234283fac539d87ce2908799b6`
Date: 2026-11-24

## Goal and first milestone

Preserve the existing browser workflow while reading the new database layout.
Start with target-name/identifier lookup and numax/dnu range searches against a
local MySQL 8 instance populated from the supplied partial dump. The first
milestone is a usable search table with uncertainties, publication and pipeline
references, sorting, pagination, and CSV export.

Remote access can be configured and verified when the server becomes available.
The local application should use the same read-only query path intended for the
remote database. Import/setup privileges are separate from runtime permissions.

## Decisions agreed with Martin

- Standardize frequency-like values and their uncertainties to ASCII `uHz` in
  the application. Treat `μHz` and `uHz` as equivalent; convert `nHz` numerically
  where applicable. Period spacings remain in seconds and inclinations in degrees.
- Preserve missing-property sentinels as `-1`. Recognize missing values before
  unit conversion so `-1 nHz` does not become `-0.001 uHz`. Exclude designated
  missing values from numerical filters, plots and summary calculations.
  Sentinel handling must be field-specific: do not reject all negative values
  globally, especially radial orders. Revisit the storage convention later.
- Use the label **Amplitude**. Defer reconciling amplitude definitions and units.
  Retain the original values and unit metadata without conversion or imposing a
  common physical unit.
- Keep `pipeline` and publication `bibcode` as separate references, including
  when they happen to contain the same code. Blank pipeline entries stay unknown.
- Remote access is read-only; the initial implementation must not require
  creating tables, views, indexes or stored procedures on the hosted database.

## Current implementation and schema mapping

The existing Flask routes in `asterocat/app.py` query a local SQLite `targets`
table with numax, dnu and teff columns, plus an `aliases` table. The browser in
`asterocat/static/index.html` provides identifier and name searches, target-list
upload, source/instrument filters, ranges, sorting, pagination, selection,
CSV export, target details with weighted summaries, plots and SIMBAD fallback.

| Current concept | New source |
| --- | --- |
| Shared target identity, currently ACAT ID | `CID` |
| Alternate names and catalogue identifiers | `cids.ID → cids.CID` |
| numax and its uncertainty | `p`, `Obsname = 'νmax'`, `value/err` |
| dnu and its uncertainty | `p`, `Obsname = 'Δν'`, `value/err` |
| Measurement publication | `bibcode` |
| Analysis pipeline reference | `pipeline` |
| Other acoustic, gravity, mixed, rotation/magnetic quantities | `p/g/mixed/rotmag` |
| Individual mode properties | `modes` |
| Temperature and observing instrument | No dedicated fields in the supplied schema |

Measurements are unique by `(CID, Obsname, pipeline, bibcode)`. A natural
displayed measurement-set key is `(CID, pipeline, bibcode)`. Preserve that
identity in selection, export, target detail and plotting to avoid merging
different analyses. Resolve aliases without multiplying rows by the number of
names attached to a star.

## Staged implementation

### 1. Local database and query layer

- Import the supplied dump into an isolated local MySQL 8 database. Keep the dump,
  database files and credentials outside git.
- Add a small Python data-access module and configurable MySQL connection.
  Keep database credentials on the Flask side.
- Implement parameterized identifier lookup through `cids`, direct CID lookup,
  and numax/dnu filtering through `p`.
- Assemble values and uncertainties by measurement-set identity. Preserve
  partially populated sets and expose available observables without inventing
  values for quantities absent from the dump.
- Normalize frequency units consistently for filters, returned values,
  uncertainties, sort order, plot axes and exports.
- Use ordinary SELECT queries initially. Measure their performance against the
  supplied dataset with its existing indexes.

### 2. First usable search interface

- Connect the existing table and search controls to the query layer.
- Support name/alias lookup, numax-only, dnu-only, combined ranges, and names
  combined with ranges.
- Display publication and pipeline separately, with bibliographic links when
  present; preserve uncertainty columns.
- Keep sorting, stable pagination, target details, row selection and CSV export.
  Ensure displayed, selected and exported records use the same filters and keys.
- Use the supplied aliases before the existing optional SIMBAD fallback.
- Keep the familiar layout. Temperature and instrument controls need an explicit
  unavailable state until their metadata source is agreed; full parity remains
  an open requirement rather than silently inferring instruments from IDs.

### 3. Restore remaining workflows

- Adapt target-list upload, plot background/foreground, box selection and exports
  to CID and measurement-set keys.
- Start plots with available quantities such as numax versus dnu.
- Adapt existing weighted summaries to missing values and missing uncertainties,
  ensuring aliases do not cause duplicate measurements to be counted.
- Complete temperature/instrument-dependent features once their source is known.
- Map other seismic observables and mode properties through the same query layer
  when extending the first search milestone; amplitude harmonization stays deferred.

### 4. Remote verification

- Confirm how the Flask host may connect to MySQL when the server returns;
  phpMyAdmin access alone does not establish direct MySQL connectivity.
- Switch connection configuration and test with read-only credentials.
- Compare identifier searches, ranges, pagination and exports against known
  local cases where the remote contents overlap.
- Measure remote latency and query plans. Add application-side caching or request
  host-managed indexes only if measurements justify that subsequent work.

## Earlier MySQL concern

The October discussion concerned materialized views: precomputed, stored query
results that can accelerate repeated searches. MySQL 8.0 does not provide native
materialized views. This does not prevent implementing name and range searches
with ordinary queries. Read-only access also means server-side schema changes
cannot be assumed.

Reference: https://dev.mysql.com/doc/refman/8.0/en/faqs-views.html

The supplied measurement-table primary keys begin with CID. Broad searches by
observable/value may therefore need substantial scanning. Measure this before
choosing an optimization or asking for additional indexes.

## Open decisions and validation

- Combined numax/dnu filtering: ask whether both must match within the same
  publication and pipeline, or may match different measurements for one star.
  The former is the proposed starting behavior because it most closely matches
  the existing row-based search. This is pending user confirmation.
- Identify the source for temperatures and observing instruments before claiming
  full feature parity.
- Validate aliases including spaces, alternate catalogue formats, and 2MASS IDs;
  a literal missing name must not return an unfiltered catalogue.
- Test missing observables, repeated publications/pipelines, boundary values,
  equivalent frequency units and `-1` sentinels.
- Verify combined-filter semantics once agreed, stable pagination without alias
  duplication, and consistent table/detail/plot/export results.
- Run integration checks on MySQL 8; SQLite-only checks cannot establish remote
  SQL compatibility.
