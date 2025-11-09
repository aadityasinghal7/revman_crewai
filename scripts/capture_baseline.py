#!/usr/bin/env python
"""
Baseline Output Capture Script
Runs the current RevMan flow and captures outputs for comparison
"""

import os
import shutil
from pathlib import Path
from datetime import datetime

# Define paths
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_DIR = DATA_DIR / "output"
BASELINE_DIR = PROJECT_ROOT / "baseline_outputs"

def capture_baseline():
    """Capture current outputs as baseline for comparison"""

    print("\n" + "=" * 60)
    print("BASELINE CAPTURE - Pre-Refactoring Outputs")
    print("=" * 60)

    # Create baseline directory
    BASELINE_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    print(f"\n[INFO] Capturing baseline outputs to: {BASELINE_DIR}")

    # Find most recent output files (they have timestamps)
    expected_files = {}

    # Excel file (no timestamp)
    excel_file = OUTPUT_DIR / "TBS Price Change Summary Report - October 13th'25_formula.xlsx"
    if excel_file.exists():
        expected_files["excel"] = excel_file

    # Find most recent timestamped files
    email_files = list(OUTPUT_DIR.glob("price_change_email_*.txt"))
    if email_files:
        expected_files["email"] = max(email_files, key=lambda p: p.stat().st_mtime)

    metadata_files = list(OUTPUT_DIR.glob("price_change_email_*_metadata.json"))
    if metadata_files:
        expected_files["metadata"] = max(metadata_files, key=lambda p: p.stat().st_mtime)

    validation_files = list(OUTPUT_DIR.glob("price_change_email_*_validation.json"))
    if validation_files:
        expected_files["validation"] = max(validation_files, key=lambda p: p.stat().st_mtime)

    # Copy outputs to baseline
    captured = []
    missing = ["excel", "email", "metadata", "validation"]

    for name, file_path in expected_files.items():
        dest = BASELINE_DIR / f"baseline_{name}{file_path.suffix}"
        shutil.copy2(file_path, dest)
        captured.append(name)
        if name in missing:
            missing.remove(name)
        print(f"  [OK] Captured {name}: {file_path.name}")

    # Save capture info
    info_path = BASELINE_DIR / f"capture_info_{timestamp}.txt"
    with open(info_path, 'w') as f:
        f.write(f"Baseline Capture: {datetime.now().isoformat()}\n")
        f.write(f"Captured files: {', '.join(captured)}\n")
        f.write(f"Missing files: {', '.join(missing)}\n")

    print(f"\n[OK] Baseline captured successfully!")
    print(f"[INFO] {len(captured)} files saved to: {BASELINE_DIR}")

    if missing:
        print(f"\n[WARN] {len(missing)} expected files not found:")
        for name in missing:
            print(f"  - {name}")
        print("\nYou may need to run the flow first to generate these outputs.")

    print("\n" + "=" * 60)
    return len(captured) > 0

if __name__ == "__main__":
    success = capture_baseline()
    exit(0 if success else 1)
