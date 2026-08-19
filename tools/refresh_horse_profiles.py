#!/usr/bin/env python3
"""Refresh fixed horse profiles from the public HKJC page without inference."""

from __future__ import annotations

import argparse
import csv
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from horse_profile_fields import (
    PROFILE_CSV_FIELDS,
    PROFILE_PARSER_VERSION,
    PROFILE_SOURCE_KIND,
    PROFILE_SOURCE_URL,
    canonicalize_row,
    merge_profile_rows,
    parse_profile_html,
    profile_completeness,
)
from tools.horse_profile_coverage import write_report


def fetch_profile(horse_no: str, retries: int = 3) -> dict[str, str]:
    url = PROFILE_SOURCE_URL.format(horse_no=horse_no)
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            request = Request(
                url,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (compatible; TianxiHorseProfileAudit/2.0; "
                        "+https://tianxi-site.pages.dev)"
                    )
                },
            )
            with urlopen(request, timeout=30) as response:
                html = response.read().decode("utf-8", errors="replace")
            parsed = parse_profile_html(html, horse_no)
            parsed.update(
                {
                    "profile_source_url": url,
                    "profile_source_kind": PROFILE_SOURCE_KIND,
                    "profile_parser_version": PROFILE_PARSER_VERSION,
                    "profile_checked_at": datetime.now(timezone.utc).isoformat(),
                    "profile_last_scraped": date.today().isoformat(),
                }
            )
            if profile_completeness(parsed) == 0:
                raise ValueError("public page returned no canonical profile fields")
            return parsed
        except Exception as exc:  # network/public-page retry boundary
            last_error = exc
            if attempt + 1 < retries:
                time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"{horse_no}: {last_error}")


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    fieldnames = list(PROFILE_CSV_FIELDS)
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fieldnames,
            extrasaction="ignore",
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)
    temp.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("horses/profiles/horse_profiles.csv"),
    )
    parser.add_argument("--status", default="active")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--horse", action="append", default=[])
    parser.add_argument(
        "--coverage-output",
        type=Path,
        default=Path("audit_reports/horse_profile_coverage_latest.json"),
    )
    args = parser.parse_args()

    with args.input.open(encoding="utf-8-sig", newline="") as handle:
        rows = [canonicalize_row(row) for row in csv.DictReader(handle)]
    by_code = {row.get("horse_no", ""): row for row in rows if row.get("horse_no")}

    if args.horse:
        codes = [code for code in args.horse if code in by_code]
    else:
        codes = [
            row["horse_no"]
            for row in rows
            if not args.status or row.get("status", "").lower() == args.status.lower()
        ]
    if args.limit:
        codes = codes[: args.limit]

    failures: list[str] = []
    refreshed = 0
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        futures = {executor.submit(fetch_profile, code): code for code in codes}
        for future in as_completed(futures):
            code = futures[future]
            try:
                parsed = future.result()
                by_code[code] = merge_profile_rows(by_code.get(code), parsed)
                refreshed += 1
                if refreshed % 50 == 0:
                    print(f"refreshed {refreshed}/{len(codes)}")
            except Exception as exc:
                failures.append(str(exc))
                print(f"FAILED {exc}")

    merged_rows = [by_code.get(row.get("horse_no", ""), row) for row in rows]
    write_csv(args.input, merged_rows)
    write_report(args.input, args.coverage_output)
    print(f"refresh complete: {refreshed}/{len(codes)}; failures={len(failures)}")
    if failures:
        Path("failed_horse_profile_refresh.log").write_text(
            "\n".join(failures) + "\n",
            encoding="utf-8",
        )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())