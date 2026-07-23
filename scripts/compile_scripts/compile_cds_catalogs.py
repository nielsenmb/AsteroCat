"""Compile CDS catalogs from declarative seismic and temperature tables."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

import numpy as np
from astropy.table import Table, join

from asterocat import utils


PARAMETERS = ("numax", "e_numax", "dnu", "e_dnu", "teff", "e_teff")
REQUIRED_FIELDS = (
    "source",
    "catalog",
    "instrument",
    "table_url",
    "teff_table_url",
    "readme_url",
    "id_column",
)


@dataclass(frozen=True)
class CatalogConfig:
    """Configuration for one pair of remote CDS tables."""

    source: str
    catalog: str
    instrument: str
    table_url: str
    teff_table_url: str
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

    @classmethod
    def from_row(cls, row: dict[str, str], row_number: int) -> "CatalogConfig":
        missing = [name for name in REQUIRED_FIELDS if not row.get(name, "").strip()]
        if missing:
            fields = ", ".join(missing)
            raise ValueError(f"Catalog row {row_number} is missing required fields: {fields}")

        values = {name: _optional(row.get(name)) for name in cls.__dataclass_fields__}
        return cls(**values)

    def column_for(self, parameter: str) -> str | None:
        return getattr(self, f"{parameter}_column")


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
        missing_columns = set(REQUIRED_FIELDS) - set(reader.fieldnames)
        if missing_columns:
            fields = ", ".join(sorted(missing_columns))
            raise ValueError(f"Catalog configuration is missing columns: {fields}")

        unknown_columns = set(reader.fieldnames) - known_fields
        if unknown_columns:
            fields = ", ".join(sorted(unknown_columns))
            raise ValueError(f"Catalog configuration has unknown columns: {fields}")

        configs = [CatalogConfig.from_row(row, line) for line, row in enumerate(reader, 2)]

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


def _merge_parameters(config: CatalogConfig, seismic, teff) -> Table:
    """Combine seismic and temperature parameters using their catalog IDs."""
    for label, table in (("seismic", seismic), ("temperature", teff)):
        if config.id_column not in table.colnames:
            raise ValueError(
                f"Configured ID column {config.id_column!r} is absent from the "
                f"{label} table; available columns: {', '.join(table.colnames)}"
            )

    seismic_parameters = Table()
    seismic_parameters[config.id_column] = seismic[config.id_column]
    for parameter in ("numax", "e_numax", "dnu", "e_dnu"):
        seismic_parameters[parameter] = _parameter_array(
            seismic, parameter, config.column_for(parameter)
        )

    teff_parameters = Table()
    teff_parameters[config.id_column] = teff[config.id_column]
    for parameter in ("teff", "e_teff"):
        teff_parameters[parameter] = _parameter_array(
            teff, parameter, config.column_for(parameter)
        )

    if config.table_url == config.teff_table_url:
        seismic_ids = np.asarray(seismic_parameters[config.id_column])
        teff_ids = np.asarray(teff_parameters[config.id_column])
        if len(seismic_ids) != len(teff_ids) or not np.array_equal(
            seismic_ids, teff_ids
        ):
            raise ValueError(
                "Separate reads of the shared seismic/temperature table "
                "returned different catalog IDs"
            )
        for parameter in ("teff", "e_teff"):
            seismic_parameters[parameter] = teff_parameters[parameter]
        return seismic_parameters

    return join(
        seismic_parameters,
        teff_parameters,
        keys=config.id_column,
        join_type="inner",
    )


def compile_catalog(
    config: CatalogConfig,
    output_dir: Path = Path("sources/json"),
    reader: Callable = utils.read_cds,
) -> Path:
    """Compile one configured CDS catalog and return its JSON path."""
    print(f"Loading {config.source} from CDS...")
    seismic = reader(config.table_url, config.readme_url)
    teff = reader(config.teff_table_url, config.readme_url)
    table = _merge_parameters(config, seismic, teff)

    parameters = {name: np.asarray(table[name], dtype=float) for name in PARAMETERS}
    valid = utils.std_input_validation(
        parameters["numax"], parameters["dnu"], parameters["teff"]
    )
    print(f"  {valid.sum()} / {len(table)} valid rows")

    targets = utils.make_targets(
        catalog_ids=table[config.id_column],
        valid_mask=valid,
        **parameters,
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
    output_dir: Path = Path("sources/json"),
) -> list[Path]:
    """Compile a sequence of configured catalogs."""
    return [compile_catalog(config, output_dir=output_dir) for config in configs]