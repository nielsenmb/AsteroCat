"""
compile_single_targets.py
-------------------------

Compile the manually curated single target list.

Required files:
    single_targets.csv

Only rows with:
    Completed entry == 1

Outputs:
    sources/single_targets.json
"""

import json
import numpy as np
import pandas as pd
from pathlib import Path
from asterocat import utils

INPUT = Path("sources/single_targets/single_targets.csv")

def main():
    print("Loading single_targets.csv...")

    data = pd.read_csv(INPUT)

    # Only use completed entries
    data = data[data["Completed entry"] == 1].copy()

    print(f"  {len(data)} completed entries")
 
    for i, row in data.iterrows():
         
        SOURCE = row["Source"] if pd.notna(row["Source"]) else None
        
        if SOURCE is None:
            continue
        
        ADS_URL = row["Source ADS"] if pd.notna(row["Source ADS"]) else None
        TEFF_ADS_URL = row["Teff Source ADS"] if pd.notna(row["Teff Source ADS"]) else None
        INSTRUMENT = row["Instrument"] if pd.notna(row["Instrument"]) else None
        CATALOG = row['Catalog']
 
        target = {"catalog_id": row["Name"],
                  "numax"     : row["νmax (μHz)"] if pd.notna(row["νmax (μHz)"]) else None, 
                  "e_numax"   : row["νmax_error (μHz)"] if pd.notna(row["νmax_error (μHz)"]) else None,
                  "dnu"       : row["Δν (μHz)"] if pd.notna(row["Δν (μHz)"]) else None,
                  "e_dnu"     : row["Δν_error (μHz)"] if pd.notna(row["Δν_error (μHz)"]) else None,
                  "teff"      : row["Teff (K)"] if pd.notna(row["Teff (K)"]) else None,
                  "e_teff"    : row["Teff_error (K)"] if pd.notna(row["Teff_error (K)"]) else None,
                 }

        targets = []
        targets.append(target)
 
        OUTPUT = Path(f"sources/{SOURCE.replace('+','').lower()}.json")

        with open(OUTPUT, "w") as f:
            json.dump({"source": SOURCE,
                       "catalog": CATALOG,
                       "instrument": INSTRUMENT,
                       "ads_url": ADS_URL,
                       "teff_ads_url": TEFF_ADS_URL,
                       "targets": targets,},f,indent=2,
            )

    print(f"Written single targets to various files.")


if __name__ == "__main__":
    main()