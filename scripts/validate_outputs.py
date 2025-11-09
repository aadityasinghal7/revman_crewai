#!/usr/bin/env python
"""
Output Validation Script
Compares current outputs against baseline to ensure refactoring doesn't change behavior
"""

import json
import difflib
from pathlib import Path

# Define paths
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_DIR = DATA_DIR / "output"
BASELINE_DIR = PROJECT_ROOT / "baseline_outputs"


def read_file_text(file_path):
    """Read text file content"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        return f"ERROR reading file: {e}"


def compare_text(baseline_text, current_text, name):
    """Compare two text strings"""
    if baseline_text == current_text:
        print(f"  [OK] {name}: EXACT MATCH")
        return True
    else:
        print(f"  [FAIL] {name}: CONTENT DIFFERS")
        # Show diff
        diff = list(difflib.unified_diff(
            baseline_text.splitlines(keepends=True),
            current_text.splitlines(keepends=True),
            fromfile='baseline',
            tofile='current',
            lineterm=''
        ))
        if diff:
            print("    Diff (first 20 lines):")
            for line in diff[:20]:
                print(f"      {line.rstrip()}")
        return False


def compare_json(baseline_path, current_path, name):
    """Compare two JSON files"""
    try:
        with open(baseline_path, 'r') as f:
            baseline_data = json.load(f)
        with open(current_path, 'r') as f:
            current_data = json.load(f)

        if baseline_data == current_data:
            print(f"  [OK] {name}: EXACT MATCH")
            return True
        else:
            print(f"  [FAIL] {name}: DATA DIFFERS")
            print(f"    Baseline: {json.dumps(baseline_data, indent=2)[:200]}...")
            print(f"    Current:  {json.dumps(current_data, indent=2)[:200]}...")
            return False
    except Exception as e:
        print(f"  [ERROR] {name}: {e}")
        return False


def compare_excel(baseline_path, current_path, name):
    """Compare Excel files (basic check)"""
    try:
        # Basic file size comparison
        baseline_size = baseline_path.stat().st_size
        current_size = current_path.stat().st_size

        # Allow 5% variance for minor differences
        size_diff_pct = abs(baseline_size - current_size) / baseline_size * 100

        if size_diff_pct < 5:
            print(f"  [OK] {name}: File sizes similar (diff: {size_diff_pct:.1f}%)")
            return True
        else:
            print(f"  [WARN] {name}: File sizes differ by {size_diff_pct:.1f}%")
            print(f"    Baseline: {baseline_size} bytes")
            print(f"    Current:  {current_size} bytes")
            return False
    except Exception as e:
        print(f"  [ERROR] {name}: {e}")
        return False


def validate_outputs():
    """Validate current outputs against baseline"""

    print("\n" + "=" * 60)
    print("OUTPUT VALIDATION - Comparing Against Baseline")
    print("=" * 60)

    if not BASELINE_DIR.exists():
        print(f"\n[ERROR] Baseline directory not found: {BASELINE_DIR}")
        print("Run 'python scripts/capture_baseline.py' first!")
        return False

    print(f"\n[INFO] Comparing outputs...")

    results = {}

    # Compare email content
    baseline_email = BASELINE_DIR / "baseline_email.txt"
    current_email_files = list(OUTPUT_DIR.glob("price_change_email_*.txt"))
    if baseline_email.exists() and current_email_files:
        current_email = max(current_email_files, key=lambda p: p.stat().st_mtime)
        baseline_text = read_file_text(baseline_email)
        current_text = read_file_text(current_email)
        results['email'] = compare_text(baseline_text, current_text, "Email Content")
    else:
        print(f"  [SKIP] Email: Missing files")
        results['email'] = None

    # Compare metadata JSON
    baseline_metadata = BASELINE_DIR / "baseline_metadata.json"
    current_metadata_files = list(OUTPUT_DIR.glob("price_change_email_*_metadata.json"))
    if baseline_metadata.exists() and current_metadata_files:
        current_metadata = max(current_metadata_files, key=lambda p: p.stat().st_mtime)
        results['metadata'] = compare_json(baseline_metadata, current_metadata, "Metadata")
    else:
        print(f"  [SKIP] Metadata: Missing files")
        results['metadata'] = None

    # Compare validation JSON
    baseline_validation = BASELINE_DIR / "baseline_validation.json"
    current_validation_files = list(OUTPUT_DIR.glob("price_change_email_*_validation.json"))
    if baseline_validation.exists() and current_validation_files:
        current_validation = max(current_validation_files, key=lambda p: p.stat().st_mtime)
        results['validation'] = compare_json(baseline_validation, current_validation, "Validation")
    else:
        print(f"  [SKIP] Validation: Missing files")
        results['validation'] = None

    # Compare Excel file
    baseline_excel = BASELINE_DIR / "baseline_excel.xlsx"
    current_excel = OUTPUT_DIR / "TBS Price Change Summary Report - October 13th'25_formula.xlsx"
    if baseline_excel.exists() and current_excel.exists():
        results['excel'] = compare_excel(baseline_excel, current_excel, "Excel File")
    else:
        print(f"  [SKIP] Excel: Missing files")
        results['excel'] = None

    # Summary
    print("\n" + "=" * 60)
    passed = sum(1 for v in results.values() if v is True)
    failed = sum(1 for v in results.values() if v is False)
    skipped = sum(1 for v in results.values() if v is None)

    print(f"SUMMARY: {passed} passed, {failed} failed, {skipped} skipped")

    if failed > 0:
        print("\n[FAIL] Some outputs differ from baseline!")
        print("Review differences above and determine if they are acceptable.")
        return False
    elif passed == 0:
        print("\n[WARN] No comparisons performed (files missing)")
        return False
    else:
        print("\n[OK] All outputs match baseline!")
        return True

    print("=" * 60)


if __name__ == "__main__":
    success = validate_outputs()
    exit(0 if success else 1)
