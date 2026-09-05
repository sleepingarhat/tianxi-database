"""
Horse Trackwork Scraper
For each horse found in race results, scrapes the full morning trackwork history
from HKJC (every training session recorded, including gallops, trotting, swimming, etc.)

Strategy:
  1. Load the horse profile page (Horse.aspx?HorseNo=XXXX)
  2. Find the "Trackwork Records" link from the navigation tabs
  3. Load that page and extract the full trackwork table

Output:
  horses/trackwork/trackwork_XXXX.csv   — full trackwork history per horse
"""

import os, re, time
import argparse
import zlib
import logging
import pandas as pd
import requests
from io import StringIO
from scraper_utils import log_failed
from comeback_detection import should_scrape
from lifecycle_helper import compute_last_race_dates, load_horse_state, load_today_entries

# Proper browser UA — HKJC sniffs "HeadlessChrome" and serves JS-shell page
# without data rows when detected. Matching Chrome on Linux bypasses this.
TRACKWORK_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36"
)
TRACKWORK_HEADERS = {
    "User-Agent": TRACKWORK_UA,
    "Accept-Language": "zh-HK,zh;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

logging.basicConfig(level=logging.INFO, format="%(message)s")

# ── CLI: shard control for parallel GHA matrix runs ─────────────────────────
# Mirrors HorseData_Scraper.py. CRC32(horse_no) % total_shards == shard.
_ap = argparse.ArgumentParser()
_ap.add_argument("--shard", type=int, default=0,
                 help="Shard index (0..total_shards-1) for matrix runs.")
_ap.add_argument("--total-shards", type=int, default=1,
                 help="Total shard count. 1 = no sharding (full pass).")
_ARGS = _ap.parse_args()
PROFILES_FILE = os.path.join("horses", "profiles", "horse_profiles.csv")

RESULTS_DIR   = "data"
TRACKWORK_DIR = os.path.join("horses", "trackwork")
FAILED_LOG    = "failed_trackwork.log"
BASE_HORSE_URL = "https://racing.hkjc.com/racing/information/Chinese/Horse/Horse.aspx?HorseNo={horse_no}"

os.makedirs(TRACKWORK_DIR, exist_ok=True)

# Direct trackwork URL constructor — bypasses the profile-page navigation
# entirely when we know the birth year. HKJC's legacy Chinese page generates
# the link only after `setLevadeNav()` fires post-load, so a naive
# time.sleep(1) was racing the JS on ~90% of runs → empty CSVs.
#   Expected format: HK_<4-digit birth year>_<horse_no>
# Source: mobile endpoint returns the same table HTML as the legacy route.
TRACKWORK_DIRECT_URL = (
    "https://racing.hkjc.com/racing/information/Chinese/Horse/"
    "TrackworkResult.aspx?HorseNo={horse_no}"
)

def build_horse_birth_year_map():
    """Map horse_no → birth year (int) from horse_profiles.csv. Tolerant of
    missing columns; returns {} so callers can fall back to DOM scraping."""
    if not os.path.exists(PROFILES_FILE):
        return {}
    try:
        df = pd.read_csv(PROFILES_FILE, encoding="utf-8-sig")
        # Column names have drifted over past scrapes; probe several spellings.
        for col in ("birth_year", "foaling_year", "year_of_birth", "出生年份"):
            if col in df.columns and "horse_no" in df.columns:
                m = {}
                for _, row in df[["horse_no", col]].dropna().iterrows():
                    try:
                        m[str(row["horse_no"]).strip()] = int(str(row[col])[:4])
                    except Exception:
                        pass
                if m:
                    return m
    except Exception as e:
        print(f"  (birth-year map unavailable: {e})")
    return {}

_BIRTH_YEAR_MAP = build_horse_birth_year_map()
print(f"Birth-year map loaded: {len(_BIRTH_YEAR_MAP)} horses")

# ── 1. Collect unique horse numbers ─────────────────────────────────────────

def extract_horse_no(horse_name_str):
    m = re.search(r"\(([A-Z]\d+)\)", horse_name_str)
    return m.group(1) if m else None

print("Scanning race results for horse numbers...")
horse_nos = set()
for year in sorted(os.listdir(RESULTS_DIR)):
    year_path = os.path.join(RESULTS_DIR, year)
    if not os.path.isdir(year_path):
        continue
    for fname in os.listdir(year_path):
        if not fname.startswith("results_"):
            continue
        try:
            df = pd.read_csv(os.path.join(year_path, fname), encoding="utf-8-sig")
            for name in df["horse_name"].dropna():
                hno = extract_horse_no(str(name))
                if hno:
                    horse_nos.add(hno)
        except Exception:
            pass

print(f"Found {len(horse_nos)} unique horses.")

# ── Shard filter (GHA matrix) — partition by CRC32(horse_no) ────────────────
# Applied BEFORE the "already done" subtraction so each shard's done/todo
# computation is scoped to its partition.
if _ARGS.total_shards > 1:
    before = len(horse_nos)
    horse_nos = {h for h in horse_nos
                 if zlib.crc32(h.encode()) % _ARGS.total_shards == _ARGS.shard}
    print(f"Shard {_ARGS.shard}/{_ARGS.total_shards}: filtered {before} → {len(horse_nos)} horses")

# Empty CSVs (header-only, ~50 bytes) indicate a failed prior scrape.
# Treating them as "done" caused 1969/1979 horses to never re-scrape.
# Re-queue them by only marking CSVs with actual data rows as done.
def _csv_has_data(path):
    try:
        with open(path, "r", encoding="utf-8-sig", errors="ignore") as fh:
            header = fh.readline()
            first_row = fh.readline().strip()
            return bool(first_row)
    except Exception:
        return False

done = set()
for f in os.listdir(TRACKWORK_DIR):
    if not f.endswith(".csv"):
        continue
    full = os.path.join(TRACKWORK_DIR, f)
    if _csv_has_data(full):
        done.add(f.replace("trackwork_", "").replace(".csv", ""))
todo_raw = sorted(horse_nos - done)
print(f"Already done: {len(done)} | Remaining (pre-filter): {len(todo_raw)}")

# ── Lifecycle filter: skip retired/inactive horses unless rescan due ────────
horse_state = load_horse_state(PROFILES_FILE)
last_race_dates = compute_last_race_dates(RESULTS_DIR)
today_entries = load_today_entries()
if today_entries:
    print(f"  Today's entry list: {len(today_entries)} horses (comeback override active)")
else:
    print("  Today's entry list: not available (comeback override inactive)")

todo = []
skipped_by_reason = {}
for hno in todo_raw:
    state = horse_state.get(hno, {})
    decision = should_scrape(
        hno,
        today_entries,
        current_status=state.get("status") or None,
        last_race_date=state.get("last_race_date") or last_race_dates.get(hno),
        profile_last_scraped=state.get("profile_last_scraped") or None,
    )
    if decision.should_scrape:
        todo.append(hno)
    else:
        skipped_by_reason[decision.reason] = skipped_by_reason.get(decision.reason, 0) + 1

skipped_total = sum(skipped_by_reason.values())
print(f"After lifecycle filter: {len(todo)} to scrape | {skipped_total} skipped")
for reason, count in sorted(skipped_by_reason.items()):
    print(f"  - skip[{reason}]: {count}")

if not todo:
    print("All horses already scraped.")
    exit(0)

# ── 2. Scrape (requests-based — bypass Selenium UA sniff) ──────────────────
# HKJC's bot detection flags `HeadlessChrome` UA and returns a JS-shell page
# with zero data rows. Selenium patches (UA spoof, webdriver flag override)
# helped intermittently. Direct HTTPS fetch with a real Chrome UA is
# deterministic: verified locally returning 5-col trackwork tables for
# L918/L920 via pd.read_html.

TRACKWORK_COLS = [
    "horse_no", "date", "work_type",
    "racecourse", "track", "venue",
    "distance", "time", "time_sec", "splits",
    "partner", "rider", "placing",
    "comment", "gear", "workout_details",
]

# ── 操練詳情解析 ────────────────────────────────────────────────────────────
# HKJC 把場地／距離／分段時間／合操馬／騎手全部塞入「操練詳情」一欄，形式有四種：
#   快操   "29.6 25.0 (54.6) (助手)"                    → 分段 + 總時間 + 騎手
#   試閘   "第2組 (徐君禮) 1200M 皮具伯樂 24.2 22.3 (1.10.52)" → 組別/騎師/距離/合操馬/時間
#   出賽   "1650M (潘頓) (5/14)"                        → 距離 + 騎師 + 名次
#   踱步   "內圈 快踱一圈 (助手)"                        → 跑道 + 內容 + 助手
# 以下把佢們拆成獨立欄位，令下游 ingest 唔再只剩日期。
_PAREN_RE   = re.compile(r"[\(（]([^\)）]*)[\)）]")
_DIST_RE    = re.compile(r"(\d{3,4})\s*[Mm]")
_GROUP_RE   = re.compile(r"第\s*(\d+)\s*組")
_PLACING_RE = re.compile(r"^\d+\s*/\s*\d+$")
_TIME_RE    = re.compile(r"^\d+(?:[.:]\d+){1,2}$")
_SPLIT_RE   = re.compile(r"(?<![\d.])(\d{1,2}\.\d)(?![\d])")


def _time_to_sec(t):
    """'54.6' → 54.6 ; '1.10.52' / '1:10.52' → 70.52"""
    if not t:
        return None
    parts = re.split(r"[.:]", t.strip())
    try:
        if len(parts) == 3:
            return int(parts[0]) * 60 + int(parts[1]) + float("0." + parts[2])
        if len(parts) == 2:
            return float(f"{parts[0]}.{parts[1]}")
        return float(t)
    except Exception:
        return None


def parse_workout_details(work_type, track, details):
    """把操練詳情拆成 距離／時間／分段／合操馬／騎手／名次／備註。"""
    out = {
        "distance": "", "time": "", "time_sec": "", "splits": "",
        "partner": "", "rider": "", "placing": "", "comment": "",
    }
    text = (details or "").strip()
    if not text:
        return out

    parens = [p.strip() for p in _PAREN_RE.findall(text) if p.strip()]
    rest = _PAREN_RE.sub(" ", text)

    for p in parens:
        if _PLACING_RE.match(p):
            out["placing"] = p.replace(" ", "")
        elif _TIME_RE.match(p):
            out["time"] = p
        elif not out["rider"]:
            out["rider"] = p

    m = _DIST_RE.search(rest)
    if m:
        out["distance"] = f"{m.group(1)}M"
        rest = rest.replace(m.group(0), " ")

    splits = _SPLIT_RE.findall(rest)
    if splits:
        out["splits"] = " ".join(splits)
        for sp in splits:
            rest = rest.replace(sp, " ", 1)
    if not out["time"] and splits:
        # 冇括號總時間時，用分段之和作參考（例如只得單段快操）
        total = sum(float(x) for x in splits)
        out["time"] = f"{total:.1f}" if len(splits) > 1 else splits[0]

    out["time_sec"] = _time_to_sec(out["time"]) or ""

    gm = _GROUP_RE.search(rest)
    if gm:
        rest = rest.replace(gm.group(0), " ")

    # 清走跑道前綴（"內圈 快踱一圈" → "快踱一圈"）
    leftover = " ".join(rest.split())
    if track and leftover.startswith(track):
        leftover = leftover[len(track):].strip()
    leftover = leftover.strip(" -－·").strip()

    if work_type in ("試閘", "出賽") and leftover:
        # 試閘／出賽：剩落嘅中文名就係合操馬
        out["partner"] = leftover
    else:
        out["comment"] = leftover
    if gm:
        grp = f"第{gm.group(1)}組"
        out["comment"] = (grp + " " + out["comment"]).strip()
    return out

SESSION = requests.Session()
SESSION.headers.update(TRACKWORK_HEADERS)


def fetch_trackwork_tables(horse_no, retries=3, backoff=2):
    """Fetch TrackworkResult page and parse all tables. Returns list of
    DataFrames or None on failure."""
    url = TRACKWORK_DIRECT_URL.format(horse_no=horse_no)
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            r = SESSION.get(url, timeout=20)
            r.raise_for_status()
            return pd.read_html(StringIO(r.text))
        except Exception as e:
            last_err = e
            if attempt < retries:
                time.sleep(backoff * attempt)
    print(f"  fetch failed after {retries} attempts: {last_err}")
    return None


def pick_trackwork_table(tables):
    """Match by expected column set:
       日期 / 晨操類別 / 馬場/跑道 / 操練詳情 / 配備
    Returns the DataFrame or None."""
    wanted = {"日期", "晨操類別", "操練詳情"}
    for t in tables:
        cols = {str(c).strip() for c in t.columns}
        if wanted.issubset(cols):
            return t
    # Fallback: sometimes the header row is row 0 instead of column names.
    for t in tables:
        if t.shape[0] > 0 and t.shape[1] >= 5:
            first_row = {str(v).strip() for v in t.iloc[0].tolist()}
            if wanted.issubset(first_row):
                # Promote row 0 to header
                new_df = t.iloc[1:].copy()
                new_df.columns = [str(v).strip() for v in t.iloc[0].tolist()]
                return new_df
    return None


for i, horse_no in enumerate(todo, 1):
    print(f"\n[{i}/{len(todo)}] Horse: {horse_no}")
    out_file = os.path.join(TRACKWORK_DIR, f"trackwork_{horse_no}.csv")

    tables = fetch_trackwork_tables(horse_no)
    if tables is None:
        log_failed(FAILED_LOG, horse_no, "fetch failed")
        continue

    table = pick_trackwork_table(tables)
    if table is None:
        print(f"  No trackwork table found (horse may have no training records)")
        pd.DataFrame(columns=TRACKWORK_COLS).to_csv(out_file, index=False, encoding="utf-8-sig")
        continue

    records = []
    for _, row in table.iterrows():
        date_val = str(row.get("日期", "")).strip()
        if not re.match(r"\d{2}/\d{2}/\d{4}", date_val):
            continue
        work_type    = str(row.get("晨操類別", "")).strip()
        location_raw = str(row.get("馬場/跑道", "")).strip()
        loc_parts    = location_raw.split(" ", 1)
        racecourse   = loc_parts[0] if loc_parts else ""
        track        = loc_parts[1] if len(loc_parts) > 1 else ""
        workout_det  = str(row.get("操練詳情", "")).strip()
        gear         = str(row.get("配備", "")).strip()
        # Normalize pandas NaN literal
        for v in ("nan", "NaN", "None"):
            if workout_det == v: workout_det = ""
            if gear == v: gear = ""

        parsed = parse_workout_details(work_type, track, workout_det)
        records.append({
            "horse_no":        horse_no,
            "date":            date_val,
            "work_type":       work_type,
            "racecourse":      racecourse,
            "track":           track,
            # venue 供下游 ingest 直接用：場地 + 跑道
            "venue":           (racecourse + (" " + track if track else "")).strip(),
            "distance":        parsed["distance"],
            "time":            parsed["time"],
            "time_sec":        parsed["time_sec"],
            "splits":          parsed["splits"],
            "partner":         parsed["partner"],
            "rider":           parsed["rider"],
            "placing":         parsed["placing"],
            "comment":         parsed["comment"] or work_type,
            "gear":            gear,
            "workout_details": workout_det,
        })

    if records:
        pd.DataFrame(records)[TRACKWORK_COLS].to_csv(out_file, index=False, encoding="utf-8-sig")
        print(f"  Saved {len(records)} trackwork sessions")
    else:
        print(f"  No trackwork records found")
        pd.DataFrame(columns=TRACKWORK_COLS).to_csv(out_file, index=False, encoding="utf-8-sig")

    # Polite throttle — HKJC occasionally rate-limits rapid sequential fetches.
    time.sleep(0.3)

print("\nHorse trackwork scraping complete!")
