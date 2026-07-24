import json

import numpy as np
import pytest
from astropy.table import Table

from scripts.compile_scripts.compile_cds_catalogs import (
    CatalogConfig,
    compile_catalog,
)


def config(**overrides):
    values = {
        "source": "Example+2026",
        "catalog": "TIC",
        "instrument": "TESS",
        "numax_table_url": "shared.dat",
        "dnu_table_url": "shared.dat",
        "teff_table_url": "shared.dat",
        "readme_url": "ReadMe",
        "ads_url": None,
        "teff_ads_url": None,
        "id_column": "TIC",
        "numax_column": "nu",
        "e_numax_column": None,
        "dnu_column": "Dnu",
        "e_dnu_column": None,
        "teff_column": "Teff",
        "e_teff_column": None,
        "expected_targets": 3,
    }
    values.update(overrides)
    return CatalogConfig(**values)


def test_shared_tables_are_read_separately_without_cartesian_join(tmp_path):
    table = Table(
        {
            "TIC": [1, 1, 2],
            "nu": [100.0, 110.0, 120.0],
            "Dnu": [10.0, 11.0, 12.0],
            "Teff": [5000.0, 5100.0, 5200.0],
        }
    )
    reads = []

    def reader(url, _readme):
        reads.append(url)
        return table

    output = compile_catalog(config(), output_dir=tmp_path, reader=reader)
    targets = json.loads(output.read_text())["targets"]

    assert reads == ["shared.dat", "shared.dat", "shared.dat"]
    assert len(targets) == 3
    assert [target["catalog_id"] for target in targets] == [1, 1, 2]
    assert [target["numax"] for target in targets] == [100.0, 110.0, 120.0]


def test_distinct_tables_are_joined_by_catalog_id(tmp_path):
    tables = {
        "numax.dat": Table({"TIC": [2, 1], "nu": [200.0, 100.0]}),
        "dnu.dat": Table({"TIC": [1, 2], "Dnu": [10.0, 20.0]}),
        "teff.dat": Table({"TIC": [2, 1], "Teff": [5200.0, 5100.0]}),
    }
    cfg = config(
        numax_table_url="numax.dat",
        dnu_table_url="dnu.dat",
        teff_table_url="teff.dat",
        expected_targets=2,
    )

    output = compile_catalog(
        cfg,
        output_dir=tmp_path,
        reader=lambda url, _readme: tables[url],
    )
    targets = json.loads(output.read_text())["targets"]

    by_id = {target["catalog_id"]: target for target in targets}
    assert by_id[1]["numax"] == 100.0
    assert by_id[1]["dnu"] == 10.0
    assert by_id[1]["teff"] == 5100.0
    assert by_id[2]["numax"] == 200.0
    assert by_id[2]["dnu"] == 20.0
    assert by_id[2]["teff"] == 5200.0


def test_expected_target_count_is_checked(tmp_path):
    table = Table(
        {
            "TIC": [1],
            "nu": [100.0],
            "Dnu": [10.0],
            "Teff": [5000.0],
        }
    )
    with pytest.raises(ValueError, match="produced 1 targets; expected 2"):
        compile_catalog(
            config(expected_targets=2),
            output_dir=tmp_path,
            reader=lambda *_: table,
        )


def test_negative_sentinels_become_missing_values(tmp_path):
    table = Table(
        {
            "TIC": [1, 2],
            "nu": [100.0, -1.0],
            "Dnu": [10.0, 20.0],
            "Teff": [5000.0, np.nan],
        }
    )
    output = compile_catalog(
        config(expected_targets=2),
        output_dir=tmp_path,
        reader=lambda *_: table,
    )
    targets = json.loads(output.read_text())["targets"]

    assert targets[1]["numax"] is None
    assert targets[1]["dnu"] == 20.0
    assert targets[1]["teff"] is None
