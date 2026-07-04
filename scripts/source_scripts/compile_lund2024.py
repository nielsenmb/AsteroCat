"""
compile_lund2024.py
-------------------
Lund et al. (2024) — K2 keystone sample, from a CSV file.

Required files:
    lund_keystone.csv

Expected columns (at minimum):
    Numax, Teff

Outputs:
    sources/lund2024.json
"""

import json
import numpy as np
import pandas as pd
from pathlib import Path
from asterocat import utils

INPUT  = Path("sources/data/lund2024/lund_keystone.csv")
ADS_URL     = "https://ui.adsabs.harvard.edu/abs/2024A%26A...688A..13L"
TEFF_ADS_URL = None
INSTRUMENT   = 'K2'
CATALOG      = 'EPIC'
SOURCE = "Lund+2024"

output = Path(f"sources/json/{SOURCE.lower().replace('+','')}.json")

def main():
    print("Loading Lund+2024 (keystone)...")
    df = pd.read_csv(INPUT)

    numax = df["Numax"].values.astype(float)
    dnu = df["Dnu"].values.astype(float)
    teff  = df["Teff"].values.astype(float)
    epic = df["ID"].str.replace(r"[A-Za-z]", "", regex=True).values.astype(int)

    e_numax = df["Numax_err"].values.astype(float) if "Numax_err" in df.columns else np.full(len(df), np.nan)
    e_dnu = df["Dnu_err"].values.astype(float) if "Dnu_err" in df.columns else np.full(len(df), np.nan)
    e_teff  = df["Teff_err"].values.astype(float)  if "Teff_err"  in df.columns else np.full(len(df), np.nan)

    valid = (((np.isfinite(numax) & (numax > 0)) | (np.isfinite(dnu) & (dnu > 0))) & (np.isnan(teff) | (teff > 0)))
    print(f"  {valid.sum()} / {len(df)} rows with finite non-zero numax or dnu")

    targets = []
    for i in np.where(valid)[0]:
        targets.append({
            "catalog_id": int(epic[i]),
            "numax":      utils.float_for_json(numax[i]), 
            "e_numax":    utils.float_for_json(e_numax[i]), 
            "dnu":        utils.float_for_json(dnu[i]), 
            "e_dnu":      utils.float_for_json(e_dnu[i]),  
            "teff":       utils.float_for_json(teff[i]),  
            "e_teff":     utils.float_for_json(e_teff[i]),  
        })

    output.parent.mkdir(exist_ok=True)
    with open(output, "w") as f:
        json.dump({"source": SOURCE, 
                   "catalog": "EPIC",
                   "instrument": INSTRUMENT,
                   "ads_url": ADS_URL, 
                   "teff_ads_url": TEFF_ADS_URL, 
                   "targets": targets}, f, indent=2)
    print(f"Written {output}  ({len(targets)} entries)")


if __name__ == "__main__":
    main()
