# AsteroCat: migration to the aarchive database

Status: local implementation complete; remote verification pending.
Branch: `new-database-layout`
Original baseline: `main` at `ddd5441accb94b234283fac539d87ce2908799b6`
Date: 2026-11-24

## Agreed scope

- Keep target-name/identifier searches, numax/dnu ranges, source selection,
  sorting, pagination, target details, target-list upload, plots and CSV exports.
- Combined numax/dnu filters must match measurements from the same star,
  publication and pipeline. Each displayed set is keyed by `(CID, bibcode, pipeline)`.
- Standardize frequency values and uncertainties to ASCII `uHz`, including numeric
  conversion from `nHz`. Preserve `-1` before conversion.
- Keep numeric missing properties as `-1` in the API and exports. Show a dash in
  tables and exclude missing values from filters, plots and weighted summaries.
  Preserve signed mode orders. Revisit the storage convention later.
- Keep Teff and its uncertainty as unavailable placeholders, with disabled
  temperature controls. No temperature data source is connected yet.
- Omit observing-instrument columns, filtering and plot coloring for now.
- Use **Amplitude** as the label and preserve the original values and unit
  metadata. Harmonizing amplitude definitions remains deferred.
- Keep pipeline and measurement-publication references separate, including when
  their bibcodes happen to match. Empty pipeline entries remain unknown.
- Use SELECT-only database access. No hosted schema changes are required.

## Implementation

`asterocat/database.py` contains name resolution, measurement-set queries,
frequency normalization and complete target details for the six-table schema.
`asterocat/app.py` serves the Flask API, CSV streaming and CLI configuration.
`asterocat/static/index.html` and `app.js` retain the browser table/plot workflow.
See [setup and usage](mysql-setup.md) for local import and connection settings.

| Concept | New source |
| --- | --- |
| Shared target identity | `CID` |
| Alternate names and catalogue identifiers | `cids.ID → cids.CID` |
| numax and its uncertainty | `p`, `Obsname = 'νmax'`, `value/err` |
| dnu and its uncertainty | `p`, `Obsname = 'Δν'`, `value/err` |
| Measurement publication | `bibcode` |
| Analysis pipeline reference | `pipeline` |
| Other seismic observables | `p/g/mixed/rotmag` |
| Individual mode properties | `modes` |
| Temperature | `-1` placeholder |

Exact name variants are tried first, followed by literal substring matching.
Aliases resolve to CIDs before measurement filtering, avoiding multiplied rows.
SIMBAD remains an optional fallback. Names and target lists use the same range
filters as ordinary searches. Empty resolved lists and empty publication
selections return no matches.

Unfiltered searches include measurement sets from every seismic table, including
sets with no numax/dnu. A range or plot axis requires its observable to be present.
Those searches join the relevant `p` rows on CID, publication and pipeline using
the existing primary key. MySQL 8 window counts avoid evaluating the full query
separately for the result total on normal pages.

## Validation

- MySQL integration fixtures exercise provenance pairing, aliases, partial sets,
  unit conversion, missing sentinels, source filters, stable pagination, read-only
  sessions and agreement between table, plot and export endpoints.
- JavaScript DOM interaction tests exercise the real Flask/MySQL path: selection
  across pages, target details, batch deduplication, source filtering, plot box
  selection and downloads. A separate opt-in Chromium test is provided.
- The supplied partial dump is used for representative searches and performance
  checks with a SELECT-only application account. Dump data and credentials are
  excluded from git.

## Earlier MySQL concern and remaining work

The October discussion concerned materialized views: stored, precomputed query
results that can accelerate searches. MySQL 8.0 has no native materialized views.
Ordinary queries implement the required searches without them.
Reference: https://dev.mysql.com/doc/refman/8.0/en/faqs-views.html

When the remote server is available, confirm its supported connection/tunnel,
configure read-only credentials and verified TLS where appropriate, and compare
known results and performance. phpMyAdmin access alone does not establish direct
MySQL connectivity. Broad unfiltered searches still aggregate the archive, so
remote performance remains to be measured before choosing caching or asking the
host for additional indexes.

Future data decisions are the Teff source, missing-value storage convention and
amplitude definitions. Observing-instrument functionality is deferred.
