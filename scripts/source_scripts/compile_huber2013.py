import json
from pathlib import Path

from astropy.table import join

from asterocat import utils

TABLE_SEISMIC = "https://cdsarc.cds.unistra.fr/ftp/J/ApJ/767/127/table1.dat"
TABLE_TEFF = "https://cdsarc.cds.unistra.fr/ftp/J/ApJ/767/127/table2.dat"
README = "https://cdsarc.cds.unistra.fr/ftp/J/ApJ/767/127/ReadMe"

ADS_URL = "https://ui.adsabs.harvard.edu/abs/2013ApJ...767..127H/"
TEFF_ADS_URL = None

INSTRUMENT = "Kepler"
CATALOG = "KIC"
SOURCE = "Huber+2013"

output = Path(f"sources/json/{SOURCE.lower().replace('+','')}.json")


def main():
    print(f"Loading {SOURCE} from CDS...")

    seismic = utils.read_cds(TABLE_SEISMIC, README)
    teff = utils.read_cds(TABLE_TEFF, README)

    table = join(seismic, teff, keys="KIC", join_type="inner")

    kic = table["KIC"]

    numax = utils.get_parameter(table, "numax")
    e_numax = utils.get_parameter(table, "e_numax")

    dnu = utils.get_parameter(table, "dnu")
    e_dnu = utils.get_parameter(table, "e_dnu")

    teff = utils.get_parameter(table, "teff")
    e_teff = utils.get_parameter(table, "e_teff")

    valid = utils.std_input_validation(numax, dnu, teff)
    print(f"  {valid.sum()} / {len(table)} valid rows")

    targets = utils.make_targets(
        catalog_ids=kic,
        numax=numax,
        e_numax=e_numax,
        dnu=dnu,
        e_dnu=e_dnu,
        teff=teff,
        e_teff=e_teff,
        valid_mask=valid,
    )

    output.parent.mkdir(exist_ok=True)

    with open(output, "w") as f:
        json.dump(
            {
                "source": SOURCE,
                "catalog": CATALOG,
                "instrument": INSTRUMENT,
                "ads_url": ADS_URL,
                "teff_ads_url": TEFF_ADS_URL,
                "targets": targets,
            },
            f,
            indent=2,
        )

    print(f"Written {output} ({len(targets)} entries)")


if __name__ == "__main__":
    main()