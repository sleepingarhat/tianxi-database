#!/usr/bin/env python3
"""Measure truthful fixed-field coverage in the HKJC horse profile archive."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from horse_profile_fields import canonicalize_row, clean_value


FIELD_READERS = {
    "countryOfOrigin": lambda row: clean_value(row.get("出生地")),
    "colour": lambda row: _colour_sex(row)[0],
    "sex": lambda row: _colour_sex(row)[1],
    "importType": lambda row: clean_value(row.get("進口類別")),
    "owner": lambda row: clean_value(row.get("馬主")),
    "sire": lambda row: clean_value(row.get("父系")),
    "dam": lambda row: clean_value(row.get("母系")),
    "damSire": lambda row: clean_value(row.get("外祖父")),
    "seasonStakes": lambda row: clean_value(row.get("今季獎金")),
    "totalStakes": lambda row: clean_value(row.get("總獎金")),
    "currentTrainer": lambda row: clean_value(row.get("練馬師")),
}


def _colour_sex(row: dict[str, str]) -> tuple[str, str]:
    parts = [part.strip() for part in clean_value(row.get("毛色___性別")).split("/", 1)]
    return (
        parts[0] if parts and parts[0] else "",
        parts[1] if len(parts) > 1 and parts[1] else "",
    )


def _coverage(rows: Iterable[dict[str, str]]) -> dict[str, object]:
    cohort = list(rows)
    total = len(cohort)
    fields: dict[str, dict[str, float | int]] = {}
    for name, reader in FIELD_READERS.items():
        present = sum(bool(reader(row)) for row in cohort)
        fields[name] = {
            "present": present,
            "missing": total - present,
            "coveragePct": round((present / total * 100) if total else 0.0, 1),
        }
    complete = sum(all(reader(row) for reader in FIELD_READERS.values()) for row in cohort)
    return {
        "horses": total,
        "completeProfiles": complete,
        "completeCoveragePct": round((complete / total * 100) if total else 0.0, 1),
        "fields": fields,
    }


def build_report(csv_path: Path) -> dict[str, object]:
    with csv_path.open(encoding="utf-8-sig", newline="") as handle:
        rows = [canonicalize_row(row) for row in csv.DictReader(handle)]
    active = [row for row in rows if clean_value(row.get("status")).lower() == "active"]
    data_dates = [
        clean_value(row.get("profile_last_scraped"))
        for row in rows
        if clean_value(row.get("profile_last_scraped"))
    ]
    return {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "source": {
            "name": "香港賽馬會公開馬匹資料",
            "archive": str(csv_path),
            "dataAsOf": max(data_dates) if data_dates else None,
        },
        "cohorts": {
            "active": _coverage(active),
            "all": _coverage(rows),
        },
    }


def write_report(csv_path: Path, output_path: Path) -> dict[str, object]:
    report = build_report(csv_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("horses/profiles/horse_profiles.csv"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("audit_reports/horse_profile_coverage_latest.json"),
    )
    args = parser.parse_args()
    report = write_report(args.input, args.output)
    active = report["cohorts"]["active"]
    print(
        f"active horses={active['horses']} "
        f"complete={active['completeProfiles']} "
        f"({active['completeCoveragePct']}%)"
    )
    for field, stats in active["fields"].items():
        print(f"  {field}: {stats['present']}/{active['horses']} ({stats['coveragePct']}%)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())