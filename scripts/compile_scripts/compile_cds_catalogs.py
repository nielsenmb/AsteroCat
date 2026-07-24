"""Compile CDS catalogs defined in ``sources/cds_catalogs.csv``."""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

import numpy as np
from astropy.table import Table, join

from asterocat import utils


DEFAULT_CONFIG = Path("sources/cds_catalogs.csv")
DEFAULT_OUTPUT_DIR = Path("sources/json")
PARAMETER_GROUPS = {
    "numax": ("numax", "e_numax"),
    "dnu": ("dnu", "e_dnu"),
    "teff": ("teff", "e_teff"),
}
PARAMETERS = tuple(
    parameter
    for group in PARAMETER_GROUPS.values()
    for parameter in group
)
REQUIRED_FIELDS = (
    "source",
    "catalog",
    "instrument",
    "readme_url",
    "id_column",
)
REQUIRED_COLUMNS = REQUIRED_FIELDS + tuple(
    f"{group}_table_url" for group in PARAMETER_GROUPS
)


@dataclass(frozen=True)
class CatalogConfig:
    """Configuration for one CDS catalog."""

    source: str
    catalog: str
    instrument: str
    numax_table_url: str | None
    dnu_table_url: str | None
    teff_table_url: str | None
    readme_url: str
    ads_url: str | None
    teff_ads_url: str | None
    id_column: str
    numax_column: str | None = None
    e_numax_column: str | None = None
    dnu_column: str | None = None
    e_dnu_column: str | None = None
    teff_column: str | None = None
    e_teff_column: str | None = None
    expected_targets: int | None = None

    @classmethod
    def from_row(cls, row: dict[str, str], row_number: int) -> "CatalogConfig":
        missing = [name for name in REQUIRED_FIELDS if not row.get(name, "").strip()]
        if missing:
            fields = ", ".join(missing)
            raise ValueError(f"Catalog row {row_number} is missing required fields: {fields}")

        if not any(_optional(row.get(f"{group}_table_url")) for group in PARAMETER_GROUPS):
            raise ValueError(
                f"Catalog row {row_number} must define at least one parameter table URL"
            )

        values = {
            name: _optional(row.get(name))
            for name in cls.__dataclass_fields__
            if name != "expected_targets"
        }
        expected_targets = _optional(row.get("expected_targets"))
        if expected_targets is not None:
            try:
                values["expected_targets"] = int(expected_targets)
            except ValueError as error:
                raise ValueError(
                    f"Catalog row {row_number} has an invalid expected_targets "
                    f"value: {expected_targets!r}"
                ) from error

        return cls(**values)

    def column_for(self, parameter: str) -> str | None:
        return getattr(self, f"{parameter}_column")

    def table_url_for(self, group: str) -> str | None:
        return getattr(self, f"{group}_table_url")


def _optional(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


def load_catalogs(path: Path) -> list[CatalogConfig]:
    """Load and validate catalog definitions from ``path``."""
    with path.open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames is None:
            raise ValueError(f"Catalog configuration is empty: {path}")

        known_fields = set(CatalogConfig.__dataclass_fields__)
        missing_columns = set(REQUIRED_COLUMNS) - set(reader.fieldnames)
        if missing_columns:
            fields = ", ".join(sorted(missing_columns))
            raise ValueError(f"Catalog configuration is missing columns: {fields}")

        unknown_columns = set(reader.fieldnames) - known_fields
        if unknown_columns:
            fields = ", ".join(sorted(unknown_columns))
            raise ValueError(f"Catalog configuration has unknown columns: {fields}")

        configs = [
            CatalogConfig.from_row(row, line)
            for line, row in enumerate(reader, 2)
        ]

    sources = [config.source for config in configs]
    duplicates = sorted({source for source in sources if sources.count(source) > 1})
    if duplicates:
        raise ValueError(f"Duplicate source definitions: {', '.join(duplicates)}")
    return configs


def source_filename(source: str) -> str:
    """Return the conventional JSON filename for a publication label."""
    return f"{source.lower().replace('+', '')}.json"


def _parameter_array(table, parameter: str, column: str | None) -> np.ndarray:
    if column is None:
        values = utils.get_parameter(table, parameter)
    else:
        if column not in table.colnames:
            raise ValueError(
                f"Configured {parameter} column {column!r} is absent; "
                f"available columns: {', '.join(table.colnames)}"
            )
        values = utils.col_to_array(table[column])

    values = np.asarray(values, dtype=float)
    # CDS commonly uses negative sentinels for missing physical quantities.
    values[(~np.isfinite(values)) | (values < 0)] = np.nan
    return values


def _parameter_table(
    config: CatalogConfig,
    group: str,
    table,
) -> Table:
    """Extract one parameter group and its catalog IDs."""
    if config.id_column not in table.colnames:
        raise ValueError(
            f"Configured ID column {config.id_column!r} is absent from the "
            f"{group} table; available columns: {', '.join(table.colnames)}"
        )

    parameters = Table()
    parameters[config.id_column] = table[config.id_column]
    for parameter in PARAMETER_GROUPS[group]:
        parameters[parameter] = _parameter_array(
            table,
            parameter,
            config.column_for(parameter),
        )
    return parameters


def _combine_shared_url(
    config: CatalogConfig,
    grouped_tables: list[tuple[str, Table]],
) -> Table:
    """Combine independently read tables from one URL row-for-row."""
    first_group, combined = grouped_tables[0]
    reference_ids = np.asarray(combined[config.id_column])

    for group, table in grouped_tables[1:]:
        ids = np.asarray(table[config.id_column])
        if len(ids) != len(reference_ids) or not np.array_equal(ids, reference_ids):
            raise ValueError(
                f"Separate reads of a shared {first_group}/{group} table "
                "returned different catalog IDs"
            )
        for parameter in PARAMETER_GROUPS[group]:
            combined[parameter] = table[parameter]

    return combined


def _require_unique_ids(config: CatalogConfig, table: Table, url: str) -> None:
    ids = np.asarray(table[config.id_column])
    if len(np.unique(ids)) != len(ids):
        raise ValueError(
            f"Cannot safely join {url!r}: {config.id_column!r} contains "
            "duplicate values. Use a bespoke compiler or provide an additional "
            "join key."
        )


def _merge_parameters(
    config: CatalogConfig,
    tables: dict[str, object],
) -> Table:
    """Combine numax, dnu, and Teff tables using their configured URLs."""
    by_url: dict[str, list[tuple[str, Table]]] = {}
    for group in PARAMETER_GROUPS:
        url = config.table_url_for(group)
        if url is None:
            continue
        parameter_table = _parameter_table(config, group, tables[group])
        by_url.setdefault(url, []).append((group, parameter_table))

    url_tables = [
        (url, _combine_shared_url(config, grouped_tables))
        for url, grouped_tables in by_url.items()
    ]
    if len(url_tables) == 1:
        return url_tables[0][1]

    for url, table in url_tables:
        _require_unique_ids(config, table, url)

    merged = url_tables[0][1]
    for _, table in url_tables[1:]:
        merged = join(
            merged,
            table,
            keys=config.id_column,
            join_type="inner",
        )
    return merged


def compile_catalog(
    config: CatalogConfig,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    reader: Callable = utils.read_cds,
) -> Path:
    """Compile one configured CDS catalog and return its JSON path."""
    print(f"Loading {config.source} from CDS...")
    tables = {
        group: reader(url, config.readme_url)
        for group in PARAMETER_GROUPS
        if (url := config.table_url_for(group)) is not None
    }
    table = _merge_parameters(config, tables)

    parameters = {
        name: (
            np.asarray(table[name], dtype=float)
            if name in table.colnames
            else np.full(len(table), np.nan)
        )
        for name in PARAMETERS
    }
    valid = utils.std_input_validation(
        parameters["numax"],
        parameters["dnu"],
        parameters["teff"],
    )
    print(f"  {valid.sum()} / {len(table)} valid rows")

    targets = utils.make_targets(
        catalog_ids=table[config.id_column],
        valid_mask=valid,
        **parameters,
    )
    if (
        config.expected_targets is not None
        and len(targets) != config.expected_targets
    ):
        raise ValueError(
            f"{config.source} produced {len(targets)} targets; "
            f"expected {config.expected_targets}"
        )

    output = output_dir / source_filename(config.source)
    utils.write_json(
        output,
        config.source,
        config.catalog,
        config.instrument,
        config.ads_url,
        config.teff_ads_url,
        targets,
    )
    return output


def compile_catalogs(
    configs: Iterable[CatalogConfig],
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> list[Path]:
    """Compile a sequence of configured catalogs."""
    return [compile_catalog(config, output_dir=output_dir) for config in configs]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "sources",
        nargs="*",
        help="Publication labels to compile (default: every configured source)",
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--list",
        action="store_true",
        help="List configured sources and exit",
    )
    args = parser.parse_args()

    configs = load_catalogs(args.config)
    if args.list:
        print("\n".join(config.source for config in configs))
        return

    if args.sources:
        by_source = {config.source: config for config in configs}
        unknown = [source for source in args.sources if source not in by_source]
        if unknown:
            parser.error(f"unknown source(s): {', '.join(unknown)}")
        configs = [by_source[source] for source in args.sources]

    passed = []
    failed = []
    for config in configs:
        try:
            compile_catalog(config, output_dir=args.output_dir)
        except Exception as error:
            failed.append(config.source)
            print(f"  ERROR: {config.source}: {error}")
        else:
            passed.append(config.source)

    print(f"Compiled {len(passed)} catalog(s); {len(failed)} failed.")
    if failed:
        print(f"Failed: {', '.join(failed)}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()