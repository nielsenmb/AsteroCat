# AsteroCat

A local browser-based tool for aggregating, cross-matching, and searching asteroseismic measurements across publications.

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

Each publication has a standalone script in `scripts/` that fetches data and writes a canonical JSON to `sources/`. Run whichever sources you want:

```bash
python scripts/compile_hatt2023.py
```

The JSON format each script must output:

```json
{
  "source": "Hatt+2023",
  "mission": "TIC",
  "targets": [
    {
      "mission_id": 12345678,
      "numax": 123.4,  "e_numax": 1.2,
      "teff": 5000.0,  "e_teff": 80.0
    }
  ]
}
```

`e_numax` and `e_teff` can be `null` if the publication doesn't provide uncertainties. `mission` accepts `TIC`/`tic`, `KIC`/`kplr`, `EPIC`/`epic`, `HD`, `HIP`.

### 2. Build the database

Scans `sources/` for all JSON files, resolves mission IDs to a common `ACAT_ID`, and writes `catalog.db`:

```bash
python scripts/build_db.py
```

**Options:**

| Flag | Default | Description |
|------|---------|-------------|
| `--sources-dir` | `sources/` | Where to look for JSON files |
| `--db` | `catalog.db` | Output database path |
| `--overrides` | `overrides.csv` | Manual cross-match corrections |
| `--log` | `build.log` | Build log path |
| `--no-resolve` | off | Skip MAST/SIMBAD lookups (fast, for testing) |

Resolution order:
1. `overrides.csv` — manual corrections always win
2. MAST TIC v8 — KIC/EPIC → TIC cross-match (batched queries)
3. SIMBAD — fallback for HD/HIP and other identifiers
4. Unresolved targets get `acat_id = NULL` and are flagged in `build.log`

Rebuild whenever you add or update a source.

### 3. Check the build log

```bash
python scripts/parse_build_log.py
```

Prints a summary of conflicts, unresolved IDs, and applied overrides. To write stub entries to `overrides.csv` for anything that needs a manual fix:

```bash
python scripts/parse_build_log.py --write-overrides
```

Then edit `overrides.csv`, uncomment the relevant lines, fill in the correct canonical ID, and rebuild.

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

Copy `scripts/compile_hatt2023.py` as a template, adapt the data loading, and make sure the output matches the JSON schema above. Then rerun `build_db.py`.

## Cross-matching

Each target gets a `catalog_id` of the form `MISSION_ID` (e.g. `TIC_12345678`, `KIC_9876543`). The build step resolves these to a shared `ACAT_ID` (e.g. `ACAT000000001`) so that the same star observed by Kepler and TESS appears as one entity in the database.

ACAT IDs are assigned sequentially at build time and are **not stable across rebuilds** — they're local identifiers, not persistent keys.

Manual corrections go in `overrides.csv` (committed to git):

```
# catalog_id, canonical_id
KIC_1234567, TIC_9876543
EPIC_211700700, TIC_8888888
```

## What's not committed to git

```
catalog.db       # regenerate with build_db.py
sources/*.json   # regenerate with compile_*.py scripts
build.log        # regenerate with build_db.py
```

`overrides.csv` **is** committed — manual corrections should be tracked.

## Project structure

```
AsteroCat/
├── asterocat/            # installable package
│   ├── app.py            # Flask server + `asterocat` CLI entry point
│   └── static/
│       └── index.html    # browser UI
├── scripts/
│   ├── build_db.py       # JSON → SQLite, with ID resolution
│   ├── parse_build_log.py
│   ├── compile_hatt2023.py
│   └── make_demo_data.py # generates synthetic data for testing
├── overrides.csv         # manual cross-match corrections
└── pyproject.toml
```
