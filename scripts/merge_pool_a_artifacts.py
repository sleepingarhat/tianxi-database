"""Merge Pool A shard artifacts into the working tree.

Each horse-data shard uploads a horse_profiles.csv equal to
[committed baseline + its shard's appended rows]. Per-horse files
(form_<hno>.csv / trackwork_<hno>.csv / injury_<hno>.csv) never collide
across shards because shards partition horse_no via CRC32.

Dedup strategy for horse_profiles.csv:
  Concat all shard copies, then drop_duplicates on horse_no keeping the
  row with the latest profile_last_scraped. This correctly prefers
  newly-scraped rows over stale baseline copies from other shards'
  fresh checkouts — even when pandas sort ordering would otherwise pick
  a stale baseline row as "last".

Usage (run from repo root):
  python scripts/merge_pool_a_artifacts.py /tmp/artifacts
"""
import shutil
import sys
from pathlib import Path

import pandas as pd


def main(art_dir: str) -> int:
    ART = Path(art_dir)
    ROOT = Path.cwd()

    if not ART.is_dir():
        print(f"artifact dir not found: {ART}", file=sys.stderr)
        return 1

    # ── 1. Copy per-horse CSVs (form_/trackwork_/injury_) ──────────────────
    # These files are partitioned by horse_no so no cross-shard collision
    # should occur. If one does (bug), the last-copy wins (benign).
    copied = {"form_records": 0, "trackwork": 0, "injury": 0}
    for subdir_name in ("form_records", "trackwork", "injury"):
        tgt = ROOT / "horses" / subdir_name
        tgt.mkdir(parents=True, exist_ok=True)
        for src in ART.rglob(f"horses/{subdir_name}/*"):
            if src.is_file() and src.name != "_horseid_map.json":
                shutil.copy2(src, tgt / src.name)
                copied[subdir_name] += 1
    for k, n in copied.items():
        print(f"  copied {n} files into horses/{k}/")

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
        if "profile_last_scraped" in concat.columns:
            concat = concat.sort_values(
                "profile_last_scraped", na_position="first"
            )
        merged = concat.drop_duplicates(subset="horse_no", keep="last")
        out = ROOT / "horses" / "profiles" / "horse_profiles.csv"
        out.parent.mkdir(parents=True, exist_ok=True)
        merged.to_csv(out, index=False, encoding="utf-8-sig")
        print(f"merged {len(dfs)} shard(s) → {len(merged)} profile rows")
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
