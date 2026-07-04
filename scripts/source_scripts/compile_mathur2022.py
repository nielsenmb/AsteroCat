
import json
from pathlib import Path
from asterocat import utils

TABLE        = "https://cdsarc.cds.unistra.fr/ftp/J/A+A/657/A31/table1.dat"
README       = "https://cdsarc.cds.unistra.fr/ftp/J/A+A/657/A31/ReadMe"
ADS_URL      = "https://ui.adsabs.harvard.edu/abs/2022A%26A...657A..31M"
TEFF_ADS_URL = None
INSTRUMENT   = 'Kepler'
CATALOG      = 'KIC'
SOURCE       = 'Mathur+2022'

output = Path(f"sources/json/{SOURCE.lower().replace('+','')}.json")

def main():
    print(f"Loading {SOURCE} from CDS...")
    table = utils.read_cds(TABLE, README)

    cat_id = table["KIC"]

    numax = utils.get_parameter(table, "numax")
    e_numax = utils.get_parameter(table, "e_numax")

    dnu = utils.get_parameter(table, "dnu")
    e_dnu = utils.get_parameter(table, "e_dnu")

    teff = utils.get_parameter(table, "teff")
    e_teff = utils.get_parameter(table, "e_teff")

    valid = utils.std_input_validation(numax, dnu, teff)
    print(f"  {valid.sum()} / {len(table)} valid rows")

    targets = utils.make_targets(
        catalog_ids=cat_id,
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