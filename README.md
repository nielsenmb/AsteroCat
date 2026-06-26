# AsteroCat

A local browser-based catalog for aggregating and searching asteroseismic measurements across publications.

## Installation

```bash
git clone https://github.com/nielsenmb/AsteroCat.git
cd AsteroCat
pip install -e .
```

## Workflow

### 1. Compile a source

Each publication has a standalone compilation script in `scripts/` that fetches data and writes a canonical JSON to `sources/`:

```bash
python scripts/compile_hatt2023.py
```

**JSON schema** (`sources/<name>.json`):
```json
{
  "source": "Hatt+2023",
  "mission": "TIC",
  "targets": [
    {
      "mission_id": 12345678,
      "numax": 123.4,   "e_numax": 1.2,
      "teff": 5000.0,   "e_teff": 80.0
    }
  ]
}
```
Fields `e_numax` and `e_teff` may be `null` if the publication doesn't provide uncertainties.

### 2. Build the database

Scans `sources/` for all JSON files and (re)builds `catalog.db`:

```bash
python scripts/build_db.py
# Options:
#   --sources-dir  PATH   (default: sources/)
#   --db           PATH   (default: catalog.db)
```

Re-run this whenever you add or update a source.

### 3. Browse

```bash
asterocat
# Options:
#   --db          PATH   path to catalog.db (default: ./catalog.db)
#   --port        INT    (default: 5000)
#   --no-browser         don't open a tab automatically
```

Opens `http://localhost:5000` in your browser.

## Adding a new source

Copy `scripts/compile_hatt2023.py` as a template, adapt the data loading, and make sure your output matches the JSON schema above. Then re-run `build_db.py`.

## Catalog ID scheme

Each target gets a `catalog_id` of the form `<MISSION>_<ID>` (e.g. `TIC_12345678`, `KIC_9876543`). A `resolved_id` column is reserved for future cross-matching across missions and publications.

## Project structure

```
AsteroCat/
├── asterocat/          # installable package
│   ├── app.py          # Flask server + CLI entry point
│   └── static/
│       └── index.html  # browser UI
├── scripts/
│   ├── build_db.py
│   ├── compile_hatt2023.py
│   └── make_demo_data.py
├── sources/            # compiled JSON files (one per publication)
├── pyproject.toml
└── README.md
```
