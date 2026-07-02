"""Generate synthetic demo JSON files for UI testing."""
import json, random, math
from pathlib import Path

random.seed(42)
Path("sources").mkdir(exist_ok=True)

SOURCES = [
    ("Hatt+2023",     "TESS",   800,   (100, 3500), (4000, 6500), "sourceadslink.com", "teffadslink.com"),
    ("Sayeed+2024",   "Kepler", 1200,  (50,  3000), (4500, 6800), "sourceadslink.com", "teffadslink.com"),
    ("Karim+2025",    "TESS",   600,   (80,  2800), (4200, 6600), "sourceadslink.com", "teffadslink.com"),
    ("Lund+2025",     "TESS",   150,   (200, 3200), (4800, 6200), "sourceadslink.com", "teffadslink.com"),
    ("Lund+2024",     "K2",     300,   (90,  2500), (4600, 6400), "sourceadslink.com", "teffadslink.com"),
    ("Sreenivas+2026","TESS",   450,   (60,  3000), (4100, 6700), "sourceadslink.com", "teffadslink.com"),
    ("Liagre+2025",   "TESS",   900,   (70,  3100), (4300, 6600), "sourceadslink.com", "teffadslink.com"),
]

CATALOG_FOR_INSTRUMENT = {"TESS": "TIC", "Kepler": "KIC", "K2": "EPIC"}

for source, instrument, n, numax_range, teff_range, ads_url, teff_ads_url in SOURCES:
    catalog = CATALOG_FOR_INSTRUMENT.get(instrument, "TIC")
    targets = []
    base_id = random.randint(100_000, 500_000)
    for i in range(n):
        numax = random.uniform(*numax_range)
        teff  = random.uniform(*teff_range)
        targets.append({
            "catalog_id": base_id + i * 7 + random.randint(0, 5),
            "numax":   round(numax, 2),
            "e_numax": round(numax * random.uniform(0.01, 0.05), 3),
            "teff":    round(teff, 1),
            "e_teff":  round(random.uniform(40, 150), 1),
        })
    slug = source.replace("+", "").lower()
    payload = {"source": source, 
               "catalog": catalog, 
               "instrument": instrument, 
               "ads_url": ads_url, 
               "teff_ads_url": teff_ads_url,
               "targets": targets}
    out = Path(f"sources/{slug}.json")
    with open(out, "w") as f:
        json.dump(payload, f)
    print(f"  {out}  {n} targets")
