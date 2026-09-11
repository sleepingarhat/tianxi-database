"""
Horse Pedigree Scraper (血統採集) — 天喜
=====================================

Purpose
-------
Keep a dedicated, always-fresh pedigree map for EVERY horse the engine may
score, especially first-starters (新馬) that have no form records yet. The LGB
pedigree features (sire_top3_sm / sire_dist_top3_sm / damsire_top3_sm) are
useless without it.

Auto-detection of new horses (no manual list needed):
  1. entries/today_entries.txt        — tomorrow's 排位表 (new horses appear here first)
  2. entries/entries_YYYY-MM-DD.txt   — dated entry archives
  3. horses/profiles/horse_profiles.csv — every profiled horse (seed source)
  4. data/<year>/results_*.csv        — every horse that ever raced
Any code from those sources that has no complete pedigree row yet is scraped.

Source
------
HKJC 馬匹資料 page (Chinese), parsed with the shared `horse_profile_fields`
parser, so labels stay in sync with HorseData_Scraper. Plain `requests` is
enough here (the profile page is server-rendered for a normal desktop UA);
no Selenium/Chrome needed, which makes this scraper cheap enough to run
before every race day.

Output
------
  data/pedigree/horse_pedigree.csv
    horse_id,code,name,sire,dam,dam_sire,half_siblings,country_of_origin,
    import_type,source_url,scraped_at
  failed_pedigree.log — codes that could not be parsed

CLI
---
  python HorsePedigree_Scraper.py                  # scrape only missing horses
  python HorsePedigree_Scraper.py --limit 200      # cap per run
  python HorsePedigree_Scraper.py --codes J514,K123
  python HorsePedigree_Scraper.py --refresh-all    # re-scrape everything
  python HorsePedigree_Scraper.py --entries-only   # only horses in today's 排位表
"""

import argparse
import csv
import glob
import os
import re
import sys
import time
from datetime import datetime, timezone

import requests

from horse_profile_fields import PROFILE_SOURCE_URL, parse_profile_html

# Kept local (not imported from scraper_utils) so this scraper needs no
# Selenium/Chrome — plain requests is enough for the profile page.
SPOOF_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


def log_failed(logfile: str, entity_id: str, reason: str = "") -> None:
    with open(logfile, "a", encoding="utf-8") as f:
        f.write(f"{datetime.now(timezone.utc).isoformat()}\t{entity_id}\t{reason}\n")

OUT_DIR = os.path.join("data", "pedigree")
OUT_CSV = os.path.join(OUT_DIR, "horse_pedigree.csv")
PROFILES_CSV = os.path.join("horses", "profiles", "horse_profiles.csv")
RESULTS_DIR = "data"
ENTRIES_DIR = "entries"
FAILED_LOG = "failed_pedigree.log"

FIELDS = [
    "horse_id",
    "code",
    "name",
    "sire",
    "dam",
    "dam_sire",
    "half_siblings",
    "country_of_origin",
    "import_type",
    "source_url",
    "scraped_at",
]

CODE_RE = re.compile(r"\b([A-Z]\d{3,4})\b")
SLEEP = float(os.environ.get("PEDIGREE_SLEEP", "0.7"))


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def clean(v) -> str:
    if v is None:
        return ""
    s = re.sub(r"\s+", " ", str(v)).strip()
    return "" if s.lower() in {"nan", "none", "null", "-", "沒有"} else s


# ── target collection ───────────────────────────────────────────────────────

def codes_from_entries() -> set[str]:
    out: set[str] = set()
    if not os.path.isdir(ENTRIES_DIR):
        return out
    paths = [os.path.join(ENTRIES_DIR, "today_entries.txt")]
    paths += sorted(glob.glob(os.path.join(ENTRIES_DIR, "entries_*.txt")))[-8:]
    for p in paths:
        if not os.path.exists(p):
            continue
        with open(p, encoding="utf-8", errors="ignore") as f:
            for line in f:
                if line.startswith("#"):
                    continue
                out.update(CODE_RE.findall(line))
    return out


def codes_from_profiles() -> set[str]:
    out: set[str] = set()
    if not os.path.exists(PROFILES_CSV):
        return out
    with open(PROFILES_CSV, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            code = clean(row.get("horse_no"))
            if code:
                out.add(code)
    return out


def codes_from_results() -> set[str]:
    out: set[str] = set()
    if not os.path.isdir(RESULTS_DIR):
        return out
    for path in glob.glob(os.path.join(RESULTS_DIR, "*", "results_*.csv")):
        try:
            with open(path, encoding="utf-8-sig", newline="") as f:
                for row in csv.DictReader(f):
                    name = row.get("horse_name") or ""
                    m = re.search(r"\(([A-Z]\d{3,4})\)", name)
                    if m:
                        out.add(m.group(1))
        except Exception as e:  # pragma: no cover
            print(f"  [warn] {path}: {e}")
    return out


# ── existing rows + seed from profiles ──────────────────────────────────────

def load_existing() -> dict[str, dict]:
    rows: dict[str, dict] = {}
    if not os.path.exists(OUT_CSV):
        return rows
    with open(OUT_CSV, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            code = clean(row.get("code"))
            if code:
                rows[code] = {k: clean(row.get(k)) for k in FIELDS}
    return rows


def seed_from_profiles(rows: dict[str, dict]) -> int:
    """horse_profiles.csv already carries 父系/母系/外祖父 for profiled horses.
    Reuse it so a first run costs zero HTTP requests for existing horses."""
    if not os.path.exists(PROFILES_CSV):
        return 0
    added = 0
    with open(PROFILES_CSV, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            code = clean(row.get("horse_no"))
            if not code:
                continue
            sire, dam, dam_sire = (
                clean(row.get("父系")),
                clean(row.get("母系")),
                clean(row.get("外祖父")),
            )
            if not (sire or dam or dam_sire):
                continue
            cur = rows.get(code)
            if cur and (cur.get("sire") or cur.get("dam_sire")):
                continue
            rows[code] = {
                "horse_id": f"horse_{code}",
                "code": code,
                "name": clean(row.get("name")),
                "sire": sire,
                "dam": dam,
                "dam_sire": dam_sire,
                "half_siblings": clean(row.get("同父系馬")),
                "country_of_origin": clean(row.get("出生地")),
                "import_type": clean(row.get("進口類別")),
                "source_url": PROFILE_SOURCE_URL.format(horse_no=code),
                "scraped_at": clean(row.get("profile_checked_at")) or now_iso(),
            }
            added += 1
    return added


def is_complete(row: dict | None) -> bool:
    return bool(row and row.get("sire") and row.get("dam"))


# ── scraping ────────────────────────────────────────────────────────────────

def fetch_pedigree(session: requests.Session, code: str) -> dict | None:
    url = PROFILE_SOURCE_URL.format(horse_no=code)
    for attempt in range(1, 4):
        try:
            resp = session.get(url, timeout=30)
            resp.raise_for_status()
            resp.encoding = resp.apparent_encoding or "utf-8"
            fields = parse_profile_html(resp.text, code)
            sire, dam, dam_sire = (
                clean(fields.get("父系")),
                clean(fields.get("母系")),
                clean(fields.get("外祖父")),
            )
            if not (sire or dam or dam_sire):
                raise ValueError("pedigree cells empty")
            return {
                "horse_id": f"horse_{code}",
                "code": code,
                "name": clean(fields.get("name")),
                "sire": sire,
                "dam": dam,
                "dam_sire": dam_sire,
                "half_siblings": clean(fields.get("同父系馬")),
                "country_of_origin": clean(fields.get("出生地")),
                "import_type": clean(fields.get("進口類別")),
                "source_url": url,
                "scraped_at": now_iso(),
            }
        except Exception as e:
            print(f"    attempt {attempt}/3 failed for {code}: {type(e).__name__}: {e}")
            if attempt < 3:
                time.sleep(2 * attempt)
    return None


def write_csv(rows: dict[str, dict]) -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    tmp = OUT_CSV + ".tmp"
    with open(tmp, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for code in sorted(rows):
            w.writerow({k: rows[code].get(k, "") for k in FIELDS})
    os.replace(tmp, OUT_CSV)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="Max horses to scrape (0 = no cap)")
    ap.add_argument("--codes", default="", help="Comma-separated codes to force scrape")
    ap.add_argument("--refresh-all", action="store_true", help="Re-scrape every known horse")
    ap.add_argument("--entries-only", action="store_true",
                    help="Only horses in the entry lists (fast pre-race-day pass)")
    args = ap.parse_args()

    rows = load_existing()
    print(f"Existing pedigree rows: {len(rows)}")

    seeded = seed_from_profiles(rows)
    if seeded:
        print(f"Seeded {seeded} rows from horse_profiles.csv (no HTTP needed)")

    if args.codes:
        targets = {c.strip().upper() for c in args.codes.split(",") if c.strip()}
    elif args.entries_only:
        targets = codes_from_entries()
    else:
        targets = codes_from_entries() | codes_from_profiles() | codes_from_results()
    print(f"Known horse codes: {len(targets)}")

    if args.refresh_all or args.codes:
        todo = sorted(targets)
    else:
        todo = sorted(c for c in targets if not is_complete(rows.get(c)))
    print(f"Missing / incomplete pedigree: {len(todo)}")

    if args.limit and len(todo) > args.limit:
        # Entry-list horses first — they are the ones the engine must score next.
        entry_codes = codes_from_entries()
        todo.sort(key=lambda c: (c not in entry_codes, c))
        todo = todo[: args.limit]
        print(f"Capped to {len(todo)} this run (entry-list horses prioritised)")

    if not todo:
        write_csv(rows)
        print("Nothing to scrape — pedigree map already complete.")
        return 0

    session = requests.Session()
    session.headers.update({"User-Agent": SPOOF_UA, "Accept-Language": "zh-HK,zh;q=0.9"})

    ok = fail = 0
    for i, code in enumerate(todo, 1):
        print(f"[{i}/{len(todo)}] {code}")
        row = fetch_pedigree(session, code)
        if row:
            rows[code] = row
            ok += 1
            print(f"    {row['name']} — 父系 {row['sire']} / 母系 {row['dam']} / 外祖父 {row['dam_sire']}")
        else:
            fail += 1
            log_failed(FAILED_LOG, code, "pedigree scrape failed")
        if i % 25 == 0:
            write_csv(rows)
        time.sleep(SLEEP)

    write_csv(rows)
    print(f"\nDone. scraped={ok} failed={fail} total_rows={len(rows)} → {OUT_CSV}")
    return 0 if ok or not todo else 1


if __name__ == "__main__":
    sys.exit(main())
