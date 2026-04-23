"""
Horse form records parser — parses the `bigborder` table on `Horse.aspx`.

Pinned 21-column schema matches Replit `horses/form_records/form_XXX.csv`
EXACTLY. HKJC supplies 19 columns; we add `horse_no` + `race_index` at the
front and split 馬場/跑道/賽道 into three separate columns.

Season header rows (e.g. "25/26 馬季") are skipped.
The "賽事重播" (race replay) column is dropped, per Replit convention.
"""
from __future__ import annotations

import re
from typing import Any

from bs4 import BeautifulSoup, Tag

from ..shared.utils import clean_text, soup as _soup, to_int

# ---------------------------------------------------------------------------
# Pinned 21-column schema (matches Replit form_XXX.csv byte-for-byte)
# ---------------------------------------------------------------------------

FORM_COLS: list[str] = [
    "horse_no",
    "race_index",
    "place",
    "date",            # DD/MM/YYYY (matches Replit convention)
    "racecourse",      # 沙田 / 跑馬地
    "track",           # 草地 / 全天候
    "course",          # A / B / C / C+3 / ...
    "distance_m",
    "going",
    "race_class",
    "draw",
    "rating",
    "trainer",
    "jockey",
    "lbw",
    "win_odds",
    "actual_wt_lbs",
    "running_position",
    "finish_time",
    "declared_wt_lbs",
    "gear",
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# 馬場 prefix → canonical Chinese racecourse name
_RACECOURSE_PREFIXES: list[tuple[str, str]] = [
    ("沙田", "沙田"),
    ("跑馬地", "跑馬地"),
    # Overseas meetings produce 2-letter race venue codes; we keep them raw
]

_TRACK_WORDS: set[str] = {"草地", "全天候", "泥地"}


def _parse_racecourse_block(block: str) -> tuple[str, str, str]:
    """
    Parse '跑馬地草地"B"' into ('跑馬地', '草地', 'B').

    Overseas / edge cases return best-effort partial values with the raw string
    kept in racecourse so downstream can inspect.
    """
    s = clean_text(block).replace("\xa0", " ")
    racecourse = ""
    track = ""
    course = ""

    # Racecourse prefix
    remainder = s
    for prefix, canonical in _RACECOURSE_PREFIXES:
        if s.startswith(prefix):
            racecourse = canonical
            remainder = s[len(prefix):].strip()
            break

    # Track (草地/全天候/泥地)
    for tw in _TRACK_WORDS:
        if tw in remainder:
            track = tw
            # strip
            remainder = remainder.replace(tw, "").strip()
            break

    # Course letter in ASCII or curly quotes
    m = re.search(r'["""]\s*([A-Z0-9+]+)\s*["""]', remainder)
    if not m:
        m = re.search(r'"\s*([A-Z0-9+]+)\s*"', remainder)
    if m:
        course = m.group(1)

    if not racecourse:
        # Overseas / unknown format — keep raw block as racecourse, leave others empty
        racecourse = s
    return racecourse, track, course


def _normalize_date(s: str) -> str:
    """'22/04/26' → '22/04/2026' (Replit convention). Return empty if unparseable."""
    s = (s or "").strip()
    m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{2,4})", s)
    if not m:
        return ""
    dd, mm, yy = m.group(1), m.group(2), m.group(3)
    year = int(yy)
    if year < 100:
        year = 2000 + year if year < 50 else 1900 + year
    return f"{int(dd):02d}/{int(mm):02d}/{year:04d}"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def parse_form_records(html: str, horse_no: str) -> list[dict[str, Any]]:
    """Return list of form-record rows (pinned FORM_COLS keys)."""
    soup = _soup(html)
    table = _find_bigborder_table(soup)
    if table is None:
        return []

    rows = table.find_all("tr")
    if len(rows) < 2:
        return []

    horse_no_u = (horse_no or "").strip().upper()
    out: list[dict[str, Any]] = []
    for tr in rows[1:]:  # skip header row
        cells = tr.find_all("td")
        if len(cells) < 18:
            # Season header ("25/26 馬季") or empty row — skip
            continue
        vals = [clean_text(c.get_text(" ", strip=True)) for c in cells]
        # Defensive: need at least 18 cells (ignore 19th/替播 col if absent)
        if len(vals) < 18:
            continue

        row: dict[str, Any] = {c: "" for c in FORM_COLS}
        row["horse_no"] = horse_no_u
        row["race_index"] = vals[0]
        row["place"] = vals[1]
        row["date"] = _normalize_date(vals[2])
        racecourse, track, course = _parse_racecourse_block(vals[3])
        row["racecourse"] = racecourse
        row["track"] = track
        row["course"] = course
        row["distance_m"] = to_int(vals[4]) if vals[4] else None
        row["going"] = vals[5]
        row["race_class"] = vals[6]
        row["draw"] = to_int(vals[7]) if vals[7] else None
        row["rating"] = to_int(vals[8]) if vals[8] else None
        row["trainer"] = vals[9]
        row["jockey"] = vals[10]
        row["lbw"] = vals[11]
        row["win_odds"] = vals[12]
        row["actual_wt_lbs"] = to_int(vals[13]) if vals[13] else None
        row["running_position"] = vals[14]
        row["finish_time"] = vals[15]
        row["declared_wt_lbs"] = to_int(vals[16]) if vals[16] else None
        row["gear"] = vals[17]
        out.append(row)
    return out


def _find_bigborder_table(soup: BeautifulSoup) -> Tag | None:
    for t in soup.find_all("table"):
        cls = t.get("class") or []
        if "bigborder" in cls:
            return t
    return None
