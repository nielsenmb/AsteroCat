"""
compile_karim2025.py
--------------------
Karim et al. (2025) — TIC targets from a whitespace-delimited text file.

Required files:
    karim2025.txt

Expected columns (comment lines start with #):
    TIC  R  Teff  numax  Dnu  PE  SNR  Cadence

Outputs:
    sources/karim2025.json
"""

import json
import numpy as np
from pathlib import Path
from asterocat import utils

INPUT  = Path("sources/data/karim2025/karim2025.txt")
ADS_URL     = "https://ui.adsabs.harvard.edu/abs/2026arXiv260524269K"
TEFF_ADS_URL = None
INSTRUMENT   = 'TESS'
CATALOG      = 'TIC'
SOURCE       = 'Karim+2025'

output = Path(f"sources/json/{SOURCE.lower().replace('+','')}.json")
def main():
    print("Loading Karim+2025...")
    data = np.genfromtxt(
        INPUT, comments="#", dtype=None, encoding="utf-8",
        names=["TIC", "R", "Teff", "numax", "Dnu", "PE", "SNR", "Cadence"],
    )

    tic   = data["TIC"].astype(int)
    numax = data["numax"].astype(float)
    dnu = data["Dnu"].astype(float)

    teff  = data["Teff"].astype(float)

    valid = (((np.isfinite(numax) & (numax > 0)) | (np.isfinite(dnu) & (dnu > 0))) & (np.isnan(teff) | (teff > 0)))
    print(f"  {valid.sum()} / {len(data)} rows with finite non-zero numax or dnu")

    targets = []
    for i in np.where(valid)[0]:
        targets.append({
            "catalog_id": int(tic[i]),
            "numax":      utils.float_for_json(numax[i]), 
            "e_numax":    None,
            "dnu":        utils.float_for_json(dnu[i]), 
            "e_dnu":      None,
            "teff":       utils.float_for_json(teff[i]), 
            "e_teff":     None,
        })

    output.parent.mkdir(exist_ok=True)
    with open(output, "w") as f:
        json.dump({"source": SOURCE, 
                   "catalog": CATALOG,
                   "instrument": INSTRUMENT,
                   "ads_url": ADS_URL, 
                   "teff_ads_url": TEFF_ADS_URL, 
                   "targets": targets}, f, indent=2)
    print(f"Written {output}  ({len(targets)} entries)")


if __name__ == "__main__":
    main()
