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

INPUT  = Path("sources/lund2024/lund_keystone.csv")
OUTPUT = Path("sources/lund2024.json")


def main():
    print("Loading Lund+2024 (keystone)...")
    df = pd.read_csv(INPUT)

    numax = df["Numax"].values.astype(float)
    teff  = df["Teff"].values.astype(float)
    epic = df["ID"].str.replace(r"[A-Za-z]", "", regex=True).values.astype(int)

    e_numax = df["e_Numax"].values.astype(float) if "e_Numax" in df.columns else np.full(len(df), np.nan)
    e_teff  = df["e_Teff"].values.astype(float)  if "e_Teff"  in df.columns else np.full(len(df), np.nan)

    valid = np.isfinite(numax) & np.isfinite(teff)
    print(f"  {valid.sum()} / {len(df)} rows with finite numax and Teff")

    targets = []
    for i in np.where(valid)[0]:
        targets.append({
            "mission_id": int(epic[i]),
            "numax":      float(numax[i]),
            "e_numax":    float(e_numax[i]) if np.isfinite(e_numax[i]) else None,
            "teff":       float(teff[i]),
            "e_teff":     float(e_teff[i])  if np.isfinite(e_teff[i])  else None,
        })

    OUTPUT.parent.mkdir(exist_ok=True)
    with open(OUTPUT, "w") as f:
        json.dump({"source": "Lund+2024", "mission": "EPIC", "targets": targets}, f, indent=2)
    print(f"Written {OUTPUT}  ({len(targets)} entries)")


if __name__ == "__main__":
    main()
