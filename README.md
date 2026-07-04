# AsteroCat

A local browser-based catalog for aggregating, cross-matching, and searching asteroseismic measurements across publications. AsteroCat compiles results from multiple sources into a single searchable database, resolves target identities across missions (Kepler/K2/TESS) and ground-based programs via MAST and SIMBAD, and provides a browser UI for searching, filtering, and exporting.

## Installation

Requires Python ≥ 3.10. We recommend using [uv](https://github.com/astral-sh/uv) for environment management.

```bash
git clone https://github.com/nielsenmb/AsteroCat.git
cd AsteroCat
uv venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
uv pip install -e .
```

Or with plain pip:

```bash
pip install -e .
```

## Workflow

### 1. Compile a source

Each publication has a standalone script in `scripts/source_scripts/` that fetches or reads data and writes a canonical JSON to `sources/json/`. Run whichever sources you want:

```bash
python scripts/source_scripts/compile_hatt2023.py
```

Raw data files (CDS tables, CSVs etc.) live in `sources/data/`.

**JSON schema** (`sources/json/<name>.json`):
```json
{
  "source":       "Hatt+2023",
  "catalog":      "TIC",
  "instrument":   "TESS",
  "ads_url":      "https://ui.adsabs.harvard.edu/abs/...",
  "teff_ads_url": "https://ui.adsabs.harvard.edu/abs/...",
  "targets": [
    {
      "catalog_id": 12345678,
      "numax":  123.4,  "e_numax": 1.2,
      "dnu":     10.1,  "e_dnu":   0.1,
      "teff":  5000.0,  "e_teff": 80.0
    }
  ]
}
```

`catalog` is the ID system (`TIC`, `KIC`, `EPIC`, `HD`, `HR`, `HIP`, `Bayer`, `Flamsteed`, `Common name`, ...). `instrument` is what observed the star (`TESS`, `Kepler`, `K2`, `HARPS@ESO3.6m`, ...). Fields `e_numax`, `dnu`, `e_dnu`, `e_teff`, `ads_url`, `teff_ads_url` are all optional and can be omitted or set to `null`.

### 2. Build the database

Scans `sources/json/` for all JSON files, resolves catalog IDs to a common `ACAT_ID`, and writes `catalog.db`:

```bash
python scripts/build_db.py
```

**Options:**

| Flag | Default | Description |
|------|---------|-------------|
| `--sources-dir` | `sources/json` | Where to look for JSON files |
| `--db` | `catalog.db` | Output database path |
| `--overrides` | `overrides.csv` | Manual cross-match corrections |
| `--log` | `build.log` | Build log path |
| `--no-resolve` | off | Skip MAST/SIMBAD resolution (fast, for testing) |
| `--overwrite` | off | Re-resolve ignoring cache. No args = all sources; named sources = those only |
| `--enrich-aliases` | off | Query SIMBAD for common-name aliases of TIC/KIC/EPIC targets. No args = all; named sources = those only |

**ID resolution** happens automatically at build time:

- `TIC`/`KIC`/`EPIC` targets → cross-matched via MAST TIC v8
- Everything else (`HD`, `Bayer`, `Common name`, etc.) → resolved via SIMBAD
- `overrides.csv` corrections always take priority
- Unresolved targets get `acat_id = NULL` and are logged to `build.log`

Rebuild whenever you add or update a source. The build is cached by JSON hash — only new or changed sources are re-resolved.

### 3. Check the build log

```bash
python scripts/parse_build_log.py
```

Summarises conflicts, unresolved IDs, and applied overrides. To write stub entries to `overrides.csv` for manual fixing:

```bash
python scripts/parse_build_log.py --write-overrides
```

### 4. Browse

```bash
asterocat
```

Opens `http://localhost:5000` in a new browser tab.

**Options:**

| Flag | Default | Description |
|------|---------|-------------|
| `--db` | `./catalog.db` | Path to database |
| `--port` | `5000` | Server port |
| `--no-browser` | off | Don't open a tab automatically |

## Adding a new source

Copy an existing script in `scripts/source_scripts/` as a template and adapt the data loading. The output must match the JSON schema above. Utilities for common operations (handling masked astropy columns, building target lists) are in `asterocat/utils.py`.

For ground-based targets, SIMBAD is queried at build time to resolve identifiers and harvest aliases (HD numbers, Bayer names, common names, etc.), so searches like "Procyon A" or "nu Indi" will find TIC/KIC entries for the same star. Run `--enrich-aliases` after building to harvest aliases for space-mission targets too.

## Cross-matching and ACAT IDs

Each target gets a `catalog_id` of the form `CATALOG_ID` (e.g. `TIC_12345678`, `KIC_9876543`, `HD_12345`, `Bayer_alfCenA`). The build step resolves these to a shared `ACAT_ID` (e.g. `ACAT000000001`) so that the same star observed by Kepler and TESS appears as one entity in the database.

ACAT IDs are assigned sequentially at build time and are **not stable across full rebuilds** — they are local identifiers, not persistent keys. Incremental builds (adding new sources) preserve existing ACAT IDs.

Manual corrections go in `overrides.csv` (committed to git):

```
# catalog_id, canonical_id
KIC_1234567, TIC_9876543
EPIC_211700700, TIC_8888888
```

## What's not committed to git

```
catalog.db        # regenerate with build_db.py
sources/json/     # regenerate with compile_*.py scripts
sources/data/     # raw data files, manage separately
build.log         # regenerate with build_db.py
```

`overrides.csv` **is** committed — manual corrections should be tracked.

## Project structure

```
AsteroCat/
├── asterocat/                  # installable package
│   ├── app.py                  # Flask server + `asterocat` CLI entry point
│   ├── utils.py                # shared utilities for compile scripts
│   └── static/
│       └── index.html          # browser UI
├── scripts/
│   ├── build_db.py             # JSON → SQLite, with ID resolution
│   ├── compile_all.py          # run all compile scripts + build_db
│   ├── parse_build_log.py      # summarise build.log conflicts
│   └── source_scripts/         # one compile script per publication
│       ├── compile_hatt2023.py
│       └── ...
├── sources/
│   ├── data/                   # raw data files (CDS tables, CSVs, etc.)
│   └── json/                   # compiled JSON files (not committed)
├── overrides.csv               # manual cross-match corrections
└── pyproject.toml
```

## Contributing

Contributions are welcome — whether that's a new source, a bug fix, or a new feature.

**Adding a new source** is the most impactful contribution. Before submitting:
1. Open an issue describing the publication (ADS link, number of targets, mission/instrument) so we can avoid duplicates and discuss any schema questions.
2. Write a compile script following the pattern in `scripts/source_scripts/`. Include the `ads_url` and `teff_ads_url` where available.
3. Submit a PR with the compile script and any raw data files needed to run it (or instructions for where to download them if they're large).

**Feature requests and bug reports**: open an issue. PRs for features are welcome but please open an issue first so we can discuss the approach.

When writing compile scripts, use the helpers in `asterocat/utils.py` (`col_to_array`, `make_targets`, `float_for_json`) rather than reimplementing the same patterns. See existing scripts for examples.
