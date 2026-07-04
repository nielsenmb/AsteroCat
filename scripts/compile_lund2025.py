"""
compile_lund2025.py
-------------------
Lund et al. (2025) — TESS luminaries, from a CSV file.

Required files:
    lund_luminaries.csv

Expected columns (at minimum):
    Numax, Teff

Outputs:
    sources/lund2025.json
"""

import json
import numpy as np
import pandas as pd
from pathlib import Path
from asterocat import utils

INPUT  = Path("sources/data/lund2025/lund_luminaries.csv")
OUTPUT = Path("sources/data/lund2025.json")
ADS_URL     = "https://ui.adsabs.harvard.edu/abs/2025A%26A...701A.285L"
TEFF_ADS_URL = None
INSTRUMENT   = 'TESS'
CATALOG      = 'TIC'
SOURCE = "Lund+2025"

output = Path(f"sources/json/{SOURCE.lower().replace('+','')}.json")

def main():
    print("Loading Lund+2025 (luminaries)...")
    df = pd.read_csv(INPUT)

    numax = df["Numax"].values.astype(float)
    dnu = df["Dnu"].values.astype(float)
    teff  = df["Teff"].values.astype(float)
    tic   = df["ID"].str.replace(r"[A-Za-z]", "", regex=True).values.astype(int)

    e_numax = df["Numax_err"].values.astype(float) if "Numax_err" in df.columns else np.full(len(df), np.nan)
    e_dnu = df["Dnu_err"].values.astype(float) if "Dnu_err" in df.columns else np.full(len(df), np.nan)
    e_teff  = df["Teff_err"].values.astype(float)  if "Teff_err"  in df.columns else np.full(len(df), np.nan)

    valid = (((np.isfinite(numax) & (numax > 0)) | (np.isfinite(dnu) & (dnu > 0))) & (np.isnan(teff) | (teff > 0)))
    print(f"  {valid.sum()} / {len(df)} rows with finite non-zero numax or dnu")

    targets = []
    for i in np.where(valid)[0]:
        targets.append({
            "catalog_id": int(tic[i]),
            "numax":      utils.float_for_json(numax[i]), 
            "e_numax":    utils.float_for_json(e_numax[i]), 
            "dnu":        utils.float_for_json(dnu[i]), 
            "e_dnu":      utils.float_for_json(e_dnu[i]),   
            "teff":       utils.float_for_json(teff[i]),  
            "e_teff":     utils.float_for_json(e_teff[i]),  
        })

    OUTPUT.parent.mkdir(exist_ok=True)
    with open(OUTPUT, "w") as f:
        json.dump({"source": SOURCE, 
                   "catalog": CATALOG,
                   "instrument": INSTRUMENT,
                   "ads_url": ADS_URL, 
                   "teff_ads_url": TEFF_ADS_URL, 
                   "targets": targets}, f, indent=2)
    print(f"Written {OUTPUT}  ({len(targets)} entries)")


if __name__ == "__main__":
    main()
