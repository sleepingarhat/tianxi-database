"""Merge Pool A shard artifacts into the working tree.

Each horse-data shard uploads a horse_profiles.csv equal to
[committed baseline + its shard's appended rows]. Per-horse files
(form_<hno>.csv / trackwork_<hno>.csv / injury_<hno>.csv) never collide
across shards because shards partition horse_no via CRC32.

Dedup strategy for horse_profiles.csv:
  Canonicalize all shard rows, order them by public-profile check time,
  then merge each horse field-by-field. A newer partial scrape can update
  values it actually found but cannot erase older verified fields.

Per-horse file merge (2026-04-30 Bug D fix):
  Each shard's artifact upload contains ALL ~5000 form/trackwork/injury
  CSVs — most at baseline from the fresh checkout, only this shard's
  ~50 horses actually updated. Old code (shutil.copy2 in rglob order)
  would have a stale baseline from one shard overwrite a fresh update
  from another. Fix: snapshot ROOT's baseline bytes FIRST, then during
  merge skip any incoming artifact file whose contents byte-match the
  baseline. Only non-baseline (= freshly-scraped by some shard) files
  get copied through.

Usage (run from repo root):
  python scripts/merge_pool_a_artifacts.py /tmp/artifacts
"""
import shutil
import sys
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from horse_profile_fields import (
    PROFILE_CSV_FIELDS,
    canonicalize_row,
    merge_profile_rows,
    profile_completeness,
)
from tools.horse_profile_coverage import write_report


def main(art_dir: str) -> int:
    ART = Path(art_dir)
    ROOT = Path.cwd()

    if not ART.is_dir():
        print(f"artifact dir not found: {ART}", file=sys.stderr)
        return 1

    # ── 1. Copy per-horse CSVs (form_/trackwork_/injury_) ──────────────────
    # Snapshot baseline FIRST so we can skip stale baseline copies from
    # shards that didn't touch a given horse. Only incoming files whose
    # bytes differ from baseline are real updates and get copied through.
    SUBDIRS = ("form_records", "trackwork", "injury")

    baseline: dict[tuple[str, str], bytes] = {}
    for subdir_name in SUBDIRS:
        tgt = ROOT / "horses" / subdir_name
        if tgt.is_dir():
            for f in tgt.iterdir():
                if f.is_file() and f.name != "_horseid_map.json":
                    try:
                        baseline[(subdir_name, f.name)] = f.read_bytes()
                    except Exception as e:
                        print(f"  baseline read failed {f}: {e}")
    print(f"  baseline snapshot: {len(baseline)} files")

    copied = {"form_records": 0, "trackwork": 0, "injury": 0}
    skipped_baseline = {"form_records": 0, "trackwork": 0, "injury": 0}
    for subdir_name in SUBDIRS:
        tgt = ROOT / "horses" / subdir_name
        tgt.mkdir(parents=True, exist_ok=True)
        for src in ART.rglob(f"horses/{subdir_name}/*"):
            if src.is_file() and src.name != "_horseid_map.json":
                try:
                    incoming = src.read_bytes()
                except Exception as e:
                    print(f"  read failed {src}: {e}")
                    continue
                if baseline.get((subdir_name, src.name)) == incoming:
                    # Stale baseline copy from a shard that didn't scrape
                    # this horse. Skip so we don't overwrite a fresh
                    # update already copied from the correct shard.
                    skipped_baseline[subdir_name] += 1
                    continue
                (tgt / src.name).write_bytes(incoming)
                copied[subdir_name] += 1
    for k in SUBDIRS:
        print(
            f"  copied {copied[k]} files into horses/{k}/ "
            f"(skipped {skipped_baseline[k]} stale-baseline)"
        )

    # ── 2. Merge horse_profiles.csv shards ────────────────────────────────
    dfs = []
    for p in ART.rglob("horse_profiles.csv"):
        try:
            dfs.append(pd.read_csv(p, encoding="utf-8-sig"))
            print(f"  loaded {p} ({len(dfs[-1])} rows)")
        except Exception as e:
            print(f"  skip {p}: {e}")

    if dfs:
        concat = pd.concat(dfs, ignore_index=True)
        records = [canonicalize_row(row) for row in concat.to_dict("records")]
        concat = pd.DataFrame(records)
        concat["_profile_sort_date"] = concat.get(
            "profile_checked_at", concat.get("profile_last_scraped", "")
        ).fillna("")
        concat["_profile_completeness"] = [
            profile_completeness(row) for row in records
        ]
        ordered = concat.sort_values(
            ["_profile_sort_date", "_profile_completeness"],
            na_position="first",
        ).drop(columns=["_profile_sort_date", "_profile_completeness"])
        merged_by_horse: dict[str, dict[str, str]] = {}
        for row in ordered.to_dict("records"):
            horse_no = str(row.get("horse_no") or "").strip()
            if not horse_no:
                continue
            merged_by_horse[horse_no] = merge_profile_rows(
                merged_by_horse.get(horse_no),
                row,
            )
        merged = pd.DataFrame(merged_by_horse.values()).reindex(
            columns=PROFILE_CSV_FIELDS
        )
        out = ROOT / "horses" / "profiles" / "horse_profiles.csv"
        out.parent.mkdir(parents=True, exist_ok=True)
        merged.to_csv(out, index=False, encoding="utf-8-sig", lineterminator="\n")
        print(f"merged {len(dfs)} shard(s) → {len(merged)} profile rows")
        report_out = ROOT / "audit_reports" / "horse_profile_coverage_latest.json"
        write_report(out, report_out)
        print(f"wrote field coverage report → {report_out}")
    else:
        print("no horse_profiles.csv shards found")

    # ── 3. Append failure logs ────────────────────────────────────────────
    for name in ("failed_horses.log", "failed_trackwork.log", "failed_injury.log"):
        dst_path = ROOT / name
        appended = 0
        with open(dst_path, "a", encoding="utf-8") as dst:
            for src in ART.rglob(name):
                try:
                    dst.write(src.read_text(encoding="utf-8"))
                    appended += 1
                except Exception as e:
                    print(f"  skip {src}: {e}")
        if appended:
            print(f"  appended {appended} {name} file(s)")

    # ── 4. Preserve injury horseid map (single copy; all shards identical) ─
    for src in ART.rglob("horses/injury/_horseid_map.json"):
        shutil.copy2(src, ROOT / "horses" / "injury" / "_horseid_map.json")
        print(f"  copied {src.name}")
        break

    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: merge_pool_a_artifacts.py <artifact-dir>", file=sys.stderr)
        sys.exit(2)
    sys.exit(main(sys.argv[1]))
