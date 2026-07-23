"""
compile_hatt2023.py
-------------------
Compilation script for Hatt et al. (2023) solar-like oscillators.

Requires:
    pip install astropy astroquery numpy

Data files:
    hatt2023/catalog.dat
    hatt2023/ReadMe.txt

Outputs:
    sources/hatt2023.json   <-- consumed by build_db.py
"""

import json
import warnings
import numpy as np
from pathlib import Path
from astropy.io import ascii
from astropy.table import vstack, join
from astroquery.mast import Catalogs
from asterocat import utils

warnings.filterwarnings("ignore")


TABLE        = Path("sources/data/hatt2023/catalog.dat")
README       = Path("sources/data/hatt2023/ReadMe.txt")
ADS_URL      = 'https://ui.adsabs.harvard.edu/abs/2023A%26A...669A..67H'
TEFF_ADS_URL = None
SOURCE       = 'Hatt+2023'
INSTRUMENT   = 'TESS'
CATALOG      = 'TIC'
BATCH        = 1000

output = Path(f"sources/json/{SOURCE.lower().replace('+','')}.json")


def chunks(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i : i + n]


def main():
    print("Loading Hatt+2023 catalog...")
    cat = ascii.read(TABLE, readme=README, format="cds")
     
    cat = cat[np.isfinite(cat["numax"])]
  
    print(f"  {len(cat)} stars with finite numax or dnu")

    tic_ids = cat["TIC"].data.tolist()

    print("Querying MAST TIC v8 for Teff...")
    rows = []
    n_batches = -(-len(tic_ids) // BATCH)
    for i, chunk in enumerate(chunks(tic_ids, BATCH)):
        t = Catalogs.query_criteria(catalog="Tic", ID=chunk)["ID", "Teff", "e_Teff"]
        rows.append(t)
        print(f"  Batch {i+1}/{n_batches}: {len(t)} rows")

    tic = vstack(rows)
    tic["TIC"] = np.array(tic["ID"], dtype=int)
    del tic["ID"]

    merged = join(cat, tic["TIC", "Teff", "e_Teff"], keys="TIC", join_type="inner")

    #merged = merged[np.isfinite(merged["Teff"])]
    print(f"  {len(merged)} stars with both numax, dnu and Teff")


    targets = []
    for row in merged:
        targets.append({
            "catalog_id": int(row["TIC"]),
            "numax":      utils.float_for_json(row['numax']), 
            "e_numax":    float(row["e_numax"])     if "e_numax" in merged.colnames and np.isfinite(row["e_numax"]) else None,
            "dnu":        utils.float_for_json(row['dnu']), 
            "e_dnu":      float(row["e_dnu"])     if "e_dnu" in merged.colnames and np.isfinite(row["e_dnu"]) else None,
            "teff":       utils.float_for_json(row["Teff"]),
            "e_teff":     utils.float_for_json(row["e_Teff"])
        })

    output.parent.mkdir(exist_ok=True)
    payload = {"source": SOURCE, 
               "catalog":    CATALOG,
               "instrument": INSTRUMENT,
               "ads_url": ADS_URL, 
               "teff_ads_url": TEFF_ADS_URL,
               "targets": targets}
    
    with open(output, "w") as f:
        json.dump(payload, f, indent=2)

    print(f"Written {output}  ({len(targets)} entries)")


if __name__ == "__main__":
    main()
