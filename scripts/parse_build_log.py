"""
parse_build_log.py
------------------
Parses build.log produced by build_db.py and summarises:
  - CONFLICT entries  (one mission ID matched multiple TIC IDs)
  - UNRESOLVED entries (no match found in MAST or SIMBAD)
  - OVERRIDE entries  (manual corrections that were applied)

Outputs a human-readable summary and optionally writes a stub overrides.csv
pre-populated with the conflicted/unresolved catalog_ids for you to fill in.

Usage:
    python scripts/parse_build_log.py [--log build.log]
                                      [--write-overrides]
                                      [--overrides overrides.csv]
"""

import argparse
import re
from pathlib import Path

# Log line patterns
RE_CONFLICT   = re.compile(r"CONFLICT: (\S+) matches multiple TIC IDs \((\d+), (\d+)\)")
RE_UNRESOLVED = re.compile(r"UNRESOLVED: (\S+)")
RE_OVERRIDE   = re.compile(r"OVERRIDE: (\S+)\s+(\S+) → (\S+)")
RE_WARNING    = re.compile(r"WARNING.*SIMBAD: no match for (.+)")


def parse(log_path: Path) -> dict:
    conflicts   = []   # (catalog_id, tic_a, tic_b)
    unresolved  = []   # catalog_id
    overrides   = []   # (catalog_id, old, new)
    simbad_miss = []   # identifier

    with open(log_path) as f:
        for line in f:
            if m := RE_CONFLICT.search(line):
                conflicts.append((m.group(1), m.group(2), m.group(3)))
            elif m := RE_UNRESOLVED.search(line):
                unresolved.append(m.group(1))
            elif m := RE_OVERRIDE.search(line):
                overrides.append((m.group(1), m.group(2), m.group(3)))
            elif m := RE_WARNING.search(line):
                simbad_miss.append(m.group(1).strip())

    return {
        "conflicts":   conflicts,
        "unresolved":  unresolved,
        "overrides":   overrides,
        "simbad_miss": simbad_miss,
    }


def print_summary(results: dict):
    conflicts   = results["conflicts"]
    unresolved  = results["unresolved"]
    overrides   = results["overrides"]
    simbad_miss = results["simbad_miss"]

    print("\n── AsteroCat build log summary ─────────────────────────────")

    if conflicts:
        print(f"\n  CONFLICTS ({len(conflicts)})  — one mission ID matched multiple TIC IDs:")
        for cid, a, b in conflicts:
            print(f"    {cid:30s}  TIC_{a}  vs  TIC_{b}")
        print("  → Add the correct TIC ID to overrides.csv and rebuild.")
    else:
        print("\n  CONFLICTS     0  ✓")

    if unresolved:
        print(f"\n  UNRESOLVED ({len(unresolved)})  — no match in MAST or SIMBAD:")
        for cid in unresolved:
            print(f"    {cid}")
        print("  → Add the correct canonical ID to overrides.csv and rebuild.")
    else:
        print("\n  UNRESOLVED    0  ✓")

    if simbad_miss:
        print(f"\n  SIMBAD misses ({len(simbad_miss)}):")
        for s in simbad_miss:
            print(f"    {s}")
    else:
        print("\n  SIMBAD misses 0  ✓")

    if overrides:
        print(f"\n  OVERRIDES APPLIED ({len(overrides)}):")
        for cid, old, new in overrides:
            print(f"    {cid:30s}  {old} → {new}")

    print("\n────────────────────────────────────────────────────────────\n")


def write_override_stubs(results: dict, overrides_path: Path):
    """
    Appends stub lines for conflicts and unresolved entries to overrides.csv.
    Lines are commented out so they don't take effect until you fill them in.
    """
    stubs = []
    for cid, a, b in results["conflicts"]:
        stubs.append(f"# CONFLICT: {cid}, ???  (TIC_{a} vs TIC_{b})")
    for cid in results["unresolved"]:
        stubs.append(f"# UNRESOLVED: {cid}, ???")

    if not stubs:
        print("No stubs to write.")
        return

    with open(overrides_path, "a") as f:
        f.write(f"\n# --- stubs added by parse_build_log.py ---\n")
        f.write("\n".join(stubs) + "\n")

    print(f"Wrote {len(stubs)} stub(s) to {overrides_path}")
    print("Edit the file, replace ??? with the correct canonical ID, uncomment, and rebuild.")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--log",             default="build.log",    type=Path)
    p.add_argument("--write-overrides", action="store_true",
                   help="Append stub lines to overrides.csv for conflicts/unresolved")
    p.add_argument("--overrides",       default="overrides.csv", type=Path)
    args = p.parse_args()

    if not args.log.exists():
        print(f"Log file not found: {args.log}")
        raise SystemExit(1)

    results = parse(args.log)
    print_summary(results)

    if args.write_overrides:
        write_override_stubs(results, args.overrides)
