"""Generate synthetic demo JSON files for UI testing."""
import json, random, math
from pathlib import Path

random.seed(42)
Path("sources").mkdir(exist_ok=True)

SOURCES = [
    ("Hatt+2023",     "TIC", 800,   (100, 3500), (4000, 6500)),
    ("Sayeed+2024",   "KIC", 1200,  (50,  3000), (4500, 6800)),
    ("Karim+2025",    "TIC", 600,   (80,  2800), (4200, 6600)),
    ("Lund+2025",     "TIC", 150,   (200, 3200), (4800, 6200)),
    ("Lund+2024",     "KIC", 300,   (90,  2500), (4600, 6400)),
    ("Sreenivas+2026","TIC", 450,   (60,  3000), (4100, 6700)),
    ("Liagre+2025",   "TIC", 900,   (70,  3100), (4300, 6600)),
]

for source, mission, n, numax_range, teff_range in SOURCES:
    targets = []
    base_id = random.randint(100_000, 500_000)
    for i in range(n):
        numax = random.uniform(*numax_range)
        teff  = random.uniform(*teff_range)
        targets.append({
            "mission_id": base_id + i * 7 + random.randint(0, 5),
            "numax":   round(numax, 2),
            "e_numax": round(numax * random.uniform(0.01, 0.05), 3),
            "teff":    round(teff, 1),
            "e_teff":  round(random.uniform(40, 150), 1),
        })
    slug = source.replace("+", "").lower()
    payload = {"source": source, "mission": mission, "targets": targets}
    out = Path(f"sources/{slug}.json")
    with open(out, "w") as f:
        json.dump(payload, f)
    print(f"  {out}  {n} targets")
