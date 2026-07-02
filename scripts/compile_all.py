"""
compile_all.py
--------------
Runs all compile_<source>.py scripts in sequence, then rebuilds catalog.db.

Any script that fails (e.g. missing input file) is skipped with a warning;
the others continue. A summary is printed at the end.

Usage:
    python scripts/compile_all.py [--no-build] [--no-resolve]

Options:
    --no-build      Skip rebuilding catalog.db after compiling
    --no-resolve    Pass --no-resolve to build_db.py (skips MAST/SIMBAD)
"""

import argparse
import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent

# Ordered list of compile scripts. Add new sources here.
COMPILE_SCRIPTS = [
    "compile_hatt2023.py",
    "compile_hon2021.py",
    "compile_hon2022.py",
    "compile_karim2025.py",
    "compile_liagre2025.py",
    "compile_lund2024.py",
    "compile_lund2025.py",
    "compile_sayeed2024.py",
    "compile_sreenivas2026.py",
    "compile_yu2018.py",
]


def run_script(script: Path, label: str) -> bool:
    print(f"\n{'─' * 60}")
    print(f"  {label}")
    print(f"{'─' * 60}")
    result = subprocess.run([sys.executable, str(script)], capture_output=False)
    if result.returncode != 0:
        print(f"  ✗ {label} failed (exit {result.returncode}) — skipping")
        return False
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-build",   action="store_true", help="Skip build_db.py after compiling")
    parser.add_argument("--no-resolve", action="store_true", help="Pass --no-resolve to build_db.py")
    parser.add_argument("--overwrite",  nargs="*", default=None, metavar="SOURCE",
                        help="Pass --overwrite to build_db.py (no args = overwrite all cached sources)")
    args = parser.parse_args()

    passed, failed = [], []

    for script_name in COMPILE_SCRIPTS:
        script = SCRIPTS_DIR / script_name
        if not script.exists():
            print(f"\n  ⚠  {script_name} not found — skipping")
            failed.append(script_name)
            continue
        ok = run_script(script, script_name)
        (passed if ok else failed).append(script_name)

    # Summary
    print(f"\n{'═' * 60}")
    print(f"  Compile summary: {len(passed)} succeeded, {len(failed)} failed")
    if failed:
        print(f"  Failed: {', '.join(failed)}")
    print(f"{'═' * 60}\n")

    if args.no_build:
        print("Skipping build_db.py (--no-build)")
        return

    if not passed:
        print("No sources compiled successfully — skipping build_db.py")
        return

    build_script = SCRIPTS_DIR / "build_db.py"
    build_args   = [sys.executable, str(build_script)]
    if args.no_resolve:
        build_args.append("--no-resolve")
    if args.overwrite is not None:
        build_args.append("--overwrite")
        build_args.extend(args.overwrite)  # empty list = overwrite all

    print(f"\n{'─' * 60}")
    print("  build_db.py")
    print(f"{'─' * 60}")
    subprocess.run(build_args)


if __name__ == "__main__":
    main()
