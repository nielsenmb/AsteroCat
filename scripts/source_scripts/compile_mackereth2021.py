import json
from pathlib import Path
import numpy as np
from asterocat import utils

TABLE = "https://cdsarc.cds.unistra.fr/ftp/J/MNRAS/502/1947/tabled1.dat.gz"
README = "https://cdsarc.cds.unistra.fr/ftp/J/MNRAS/502/1947/ReadMe"

ADS_URL = "https://ui.adsabs.harvard.edu/abs/2021MNRAS.502.1947M"
TEFF_ADS_URL = None

INSTRUMENT = "TESS"
CATALOG = "TIC"
SOURCE = "Mackereth+2021"

output = Path(f"sources/json/{SOURCE.lower().replace('+','')}.json")


def main():
    print(f"Loading {SOURCE} from CDS...")
    table = utils.read_cds(TABLE, README)
    
    for col in ['numaxmean', 'e_numaxmean', 'dnumean', 'e_dnumean', 'TeffAPO', 'e_TeffAPO']:
        data = table[col]
        mask = (data < 0) | ~np.isfinite(data)
        table[col][mask] = np.nan

    tic = table["TIC"]

    numax = utils.get_parameter(table, "numax")
    e_numax = utils.get_parameter(table, "e_numax")

    dnu = utils.get_parameter(table, "dnu")
    e_dnu = utils.get_parameter(table, "e_dnu")

    teff = utils.get_parameter(table, "teff")
    e_teff = utils.get_parameter(table, "e_teff")

    valid = utils.std_input_validation(numax, dnu, teff)
    print(f"  {valid.sum()} / {len(table)} valid rows")

    targets = utils.make_targets(
        catalog_ids=tic,
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