#!/usr/bin/env python3
"""Simple local validator for declaration files.

Usage:
  python validate_declaration.py path/to/declaration.txt

This script checks for required fields, order (best-effort), and basic value formats.
It does NOT send data anywhere.
"""
import re
import sys

REQUIRED_FIELDS = [
    "SENDER_ID",
    "ORIGIN",
    "DESTINATION",
    "WEIGHT_KG",
    "BUDGET_PP",
    "CONTENT_DESCRIPTION",
]

FIELD_RE = re.compile(r"^(?P<key>[A-Z_]+):\s*(?P<val>.*)$")


def parse_lines(lines):
    fields = []
    for ln in lines:
        ln = ln.strip()
        if not ln or ln.startswith("====") or ln.startswith("---"):
            continue
        m = FIELD_RE.match(ln)
        if m:
            fields.append((m.group("key"), m.group("val")))
    return fields


def validate(fields):
    keys = [k for k, _ in fields]
    report = []
    ok = True

    # Check presence
    for rf in REQUIRED_FIELDS:
        if rf not in keys:
            report.append(f"MISSING FIELD: {rf}")
            ok = False

    # Basic order check: ensure required fields appear in the same relative order
    idx_map = {k: i for i, k in enumerate(keys)}
    last_idx = -1
    for rf in REQUIRED_FIELDS:
        if rf in idx_map:
            if idx_map[rf] <= last_idx:
                report.append(f"ORDERING WARNING: {rf} appears out of expected order")
                ok = False
            last_idx = idx_map[rf]

    # Basic value checks
    val_map = {k: v for k, v in fields}
    if "WEIGHT_KG" in val_map:
        w = val_map["WEIGHT_KG"].strip()
        try:
            float(w)
        except Exception:
            report.append("INVALID WEIGHT_KG: not a number")
            ok = False

    if "BUDGET_PP" in val_map:
        b = val_map["BUDGET_PP"].strip()
        if b and not (b.isdigit() or b.upper() == "SYSTEM"):
            report.append("INVALID BUDGET_PP: expected integer or 'SYSTEM'")
            ok = False

    return ok, report


def main():
    if len(sys.argv) != 2:
        print("Usage: python validate_declaration.py path/to/declaration.txt")
        sys.exit(2)

    path = sys.argv[1]
    try:
        with open(path, encoding="utf-8") as f:
            lines = f.readlines()
    except Exception as e:
        print(f"ERROR: cannot open file: {e}")
        sys.exit(3)

    fields = parse_lines(lines)
    ok, report = validate(fields)

    print("Validation result:")
    if ok:
        print("  OK — basic checks passed (no sensitive-data checks performed).")
    else:
        print("  FAILED — issues found:")
        for r in report:
            print("   -", r)

    # Print parsed fields summary
    print("\nParsed fields:")
    for k, v in fields:
        print(f"  {k}: {v}")

    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
