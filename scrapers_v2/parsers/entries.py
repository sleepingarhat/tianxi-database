"""
Entries (Racecard) parser — `RaceCard.aspx` 排位表 SSR HTML.

Replaces Replit's Selenium entries scraper. Source URL pattern:
    https://racing.hkjc.com/racing/information/chinese/Racing/RaceCard.aspx
      ?RaceDate=YYYY/MM/DD&Racecourse=ST|HV&RaceNo=<n>

Two outputs per race:
  - race_meta:  one row describing the race (date, venue, course, dist, class, prize)
  - entries:    N rows (one per starter + reserves) with the 27 pinned fields

Column schema is PINNED (no dynamic inference from HTML) so downstream CSVs
never drift. HKJC layout changes will cause explicit KeyError, not silent data loss.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from bs4 import BeautifulSoup, Tag

from ..shared.utils import (
    clean_text,
    soup as _soup,
    to_float,
    to_int,
)

# Venue detection — search anywhere in meta block (not just leading token)
VENUE_ZH_TO_CODE: dict[str, str] = {
    "沙田": "ST",
    "跑馬地": "HV",
}

# ---------------------------------------------------------------------------
# Pinned column schemas
# ---------------------------------------------------------------------------

RACE_META_COLS: list[str] = [
    "race_date",         # YYYY-MM-DD
    "venue",             # 沙田 / 跑馬地
    "venue_code",        # ST / HV
    "race_no",           # int
    "race_name",         # e.g. "洛神花讓賽"
    "race_time",         # HH:MM
    "surface",           # 草地 / 全天候
    "course",            # A / B / C / C+3 ...
    "distance_m",        # int
    "going",             # 好地至快地 / 快地 / ...
    "prize_hkd",         # int
    "rating_band",       # e.g. "80-60"
    "race_class",        # e.g. "第三班"
    "source_url",
]

ENTRY_COLS: list[str] = [
    # Identity
    "race_date",
    "venue_code",
    "race_no",
    "horse_no",          # 1..14
    "is_reserve",        # 0/1
    # Horse
    "horse_id",          # HK_YYYY_XXXX
    "horse_name",
    "recent_form",       # "1/4/4/2/1/2"
    "brand_no",          # 烙號 e.g. K056
    # Carrying
    "weight_carried_lbs",
    "possible_over_weight",
    "draw",
    # Connections
    "jockey_id",
    "jockey_name",
    "trainer_id",
    "trainer_name",
    # Ratings / form
    "international_rating",
    "rating",
    "rating_delta",
    "declared_weight_lbs",
    "weight_delta",
    "best_time",
    # Bio
    "horse_age",
    "age_allowance",
    "sex",
    "season_winnings_hkd",
    "priority",          # 優先參賽次序
    "days_since_last_run",
    "gear",              # "SR/TT"
    "owner",
    "sire",
    "dam",
    "import_type",       # PP / PPG / ...
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ID_HORSE_RE = re.compile(r"horseid=([A-Z0-9_]+)", re.I)
_ID_JOCKEY_RE = re.compile(r"jockeyid=([A-Z0-9]+)", re.I)
_ID_TRAINER_RE = re.compile(r"trainerid=([A-Z0-9]+)", re.I)
_DIST_RE = re.compile(r"(\d{3,4})\s*米")
_PRIZE_RE = re.compile(r"獎金[:：]\s*\$?([\d,]+)")
_RATING_RE = re.compile(r"評分[:：]\s*([\d\-]+)")
_CLASS_RE = re.compile(r"(第[一二三四五六]班|國際一級|國際二級|國際三級|第\d+班|賽事)")
_COURSE_RE = re.compile(r'"?([A-Z](?:\+\d)?)"?\s*賽道')
_RACE_NO_RE = re.compile(r"第\s*(\d+)\s*場")
_DATE_RE = re.compile(r"(\d{4})年(\d{1,2})月(\d{1,2})日")
_TIME_RE = re.compile(r"\b(\d{1,2}:\d{2})\b")
_SURFACE_RE = re.compile(r"(草地|全天候)")


def _id_from_href(href: str, pattern: re.Pattern[str]) -> str:
    if not href:
        return ""
    m = pattern.search(href)
    return m.group(1) if m else ""


def _extract_meta_block(soup: BeautifulSoup) -> str:
    """Get the concatenated text of the race info block (first `.f_fs13`)."""
    for el in soup.select(".f_fs13"):
        txt = el.get_text(" ", strip=True)
        if "第" in txt and "場" in txt and ("米" in txt or "公尺" in txt):
            return txt
    return ""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


@dataclass
class RacecardParse:
    meta: dict[str, Any]
    entries: list[dict[str, Any]]


def parse_racecard(html: str, source_url: str = "") -> RacecardParse:
    """Parse one RaceCard.aspx page. Returns meta + list of entry rows."""
    soup = _soup(html)
    meta = _parse_meta(soup, source_url)
    entries = _parse_starters(soup, meta)
    entries.extend(_parse_reserves(soup, meta))
    return RacecardParse(meta=meta, entries=entries)


# ---------------------------------------------------------------------------
# Meta parsing
# ---------------------------------------------------------------------------


def _parse_meta(soup: BeautifulSoup, source_url: str) -> dict[str, Any]:
    text = _extract_meta_block(soup)
    meta: dict[str, Any] = {k: "" for k in RACE_META_COLS}
    meta["source_url"] = source_url

    if not text:
        return meta

    # race_no
    m = _RACE_NO_RE.search(text)
    meta["race_no"] = to_int(m.group(1)) if m else None

    # race_name — between "場 - " and the date (or venue)
    name_match = re.search(r"第\s*\d+\s*場\s*-\s*(.+?)\s+\d{4}年", text)
    if name_match:
        meta["race_name"] = clean_text(name_match.group(1))

    # race_date
    m = _DATE_RE.search(text)
    if m:
        y, mm, dd = m.groups()
        meta["race_date"] = f"{y}-{int(mm):02d}-{int(dd):02d}"

    # venue — search anywhere in the meta paragraph
    for zh, code in VENUE_ZH_TO_CODE.items():
        if zh in text:
            meta["venue"] = zh
            meta["venue_code"] = code
            break
    # course letter
    m = _COURSE_RE.search(text)
    if m:
        meta["course"] = m.group(1)

    # race_time
    m = _TIME_RE.search(text)
    if m:
        meta["race_time"] = m.group(1)

    # surface
    m = _SURFACE_RE.search(text)
    if m:
        meta["surface"] = m.group(1)

    # distance
    m = _DIST_RE.search(text)
    if m:
        meta["distance_m"] = to_int(m.group(1))

    # going — whatever follows the course/distance marker up to "獎金"
    going_match = re.search(r"米\s*,?\s*(.+?)\s*獎金", text)
    if going_match:
        meta["going"] = clean_text(going_match.group(1))

    # prize
    m = _PRIZE_RE.search(text)
    if m:
        meta["prize_hkd"] = to_int(m.group(1).replace(",", ""))

    # rating band
    m = _RATING_RE.search(text)
    if m:
        meta["rating_band"] = m.group(1)

    # race_class
    m = _CLASS_RE.search(text)
    if m:
        meta["race_class"] = m.group(1)

    return meta


# ---------------------------------------------------------------------------
# Starter table
# ---------------------------------------------------------------------------


def _find_starter_table(soup: BeautifulSoup) -> Tag | None:
    for t in soup.find_all("table"):
        cls = t.get("class") or []
        if "starter" in cls:
            return t
    return None


def _parse_starters(soup: BeautifulSoup, meta: dict[str, Any]) -> list[dict[str, Any]]:
    table = _find_starter_table(soup)
    if table is None:
        return []
    rows = table.find_all("tr")
    if len(rows) < 2:
        return []

    header_cells = rows[0].find_all(["th", "td"])
    headers = [clean_text(c.get_text()) for c in header_cells]
    col_idx = _build_header_index(headers)

    out: list[dict[str, Any]] = []
    for tr in rows[1:]:
        cells = tr.find_all("td")
        if len(cells) < 5:
            continue
        entry = _row_to_entry(cells, col_idx, meta, is_reserve=False)
        if entry:
            out.append(entry)
    return out


def _parse_reserves(soup: BeautifulSoup, meta: dict[str, Any]) -> list[dict[str, Any]]:
    """Reserves table - same schema but flagged is_reserve=1."""
    # HKJC uses a plain table right after the 後備馬匹 heading; usually class='tableBorderBlue'.
    for t in soup.find_all("table"):
        txt = t.get_text(" ", strip=True)
        if "後備馬匹" in txt and "馬匹編號" in txt:
            rows = t.find_all("tr")
            # find header row that contains "馬匹編號"
            hdr_i = next((i for i, r in enumerate(rows) if "馬匹編號" in r.get_text()), -1)
            if hdr_i < 0:
                continue
            header_cells = rows[hdr_i].find_all(["th", "td"])
            headers = [clean_text(c.get_text()) for c in header_cells]
            col_idx = _build_header_index(headers)
            out: list[dict[str, Any]] = []
            for tr in rows[hdr_i + 1:]:
                cells = tr.find_all("td")
                if len(cells) < 5:
                    continue
                entry = _row_to_entry(cells, col_idx, meta, is_reserve=True)
                if entry:
                    out.append(entry)
            return out
    return []


# Header-name -> pinned field mapping
_HDR_MAP: dict[str, str] = {
    "馬匹編號": "horse_no",
    "6次近績": "recent_form",
    "近績": "recent_form",
    "馬名": "horse_name",
    "烙號": "brand_no",
    "負磅": "weight_carried_lbs",
    "騎師": "jockey_name",
    "可能超磅": "possible_over_weight",
    "檔位": "draw",
    "練馬師": "trainer_name",
    "國際評分": "international_rating",
    "評分": "rating",
    "評分+/-": "rating_delta",
    "排位體重": "declared_weight_lbs",
    "排位體重+/-": "weight_delta",
    "最佳時間": "best_time",
    "馬齡": "horse_age",
    "分齡讓磅": "age_allowance",
    "性別": "sex",
    "今季獎金": "season_winnings_hkd",
    "優先參賽次序": "priority",
    "上賽距今日數": "days_since_last_run",
    "配備": "gear",
    "馬主": "owner",
    "父系": "sire",
    "母系": "dam",
    "進口類別": "import_type",
}


def _build_header_index(headers: list[str]) -> dict[str, int]:
    idx: dict[str, int] = {}
    for i, h in enumerate(headers):
        key = _HDR_MAP.get(h)
        if key and key not in idx:
            idx[key] = i
    return idx


_INT_FIELDS = {
    "horse_no", "weight_carried_lbs", "draw", "rating", "declared_weight_lbs",
    "horse_age", "days_since_last_run", "priority",
}
_FLOAT_FIELDS: set[str] = set()  # best_time kept as string "1.08.49"
_MONEY_FIELDS = {"season_winnings_hkd"}


def _coerce(field: str, raw: str) -> Any:
    if raw == "" or raw == "-":
        return None if field in _INT_FIELDS or field in _MONEY_FIELDS else ""
    if field in _MONEY_FIELDS:
        return to_int(raw.replace(",", ""))
    if field in _INT_FIELDS:
        return to_int(raw)
    if field in _FLOAT_FIELDS:
        return to_float(raw)
    return raw


def _row_to_entry(
    cells: list[Tag],
    col_idx: dict[str, int],
    meta: dict[str, Any],
    *,
    is_reserve: bool,
) -> dict[str, Any] | None:
    e: dict[str, Any] = {c: "" for c in ENTRY_COLS}
    e["race_date"] = meta.get("race_date", "")
    e["venue_code"] = meta.get("venue_code", "")
    e["race_no"] = meta.get("race_no")
    e["is_reserve"] = 1 if is_reserve else 0

    for field, i in col_idx.items():
        if i >= len(cells):
            continue
        raw = clean_text(cells[i].get_text())
        e[field] = _coerce(field, raw)

    # Drop empty rows (no horse_no or no horse_name)
    if not e.get("horse_no") and not e.get("horse_name"):
        return None

    # Extract IDs from anchor hrefs in relevant cells
    horse_cell = cells[col_idx.get("horse_name", -1)] if col_idx.get("horse_name") is not None else None
    jockey_cell = cells[col_idx.get("jockey_name", -1)] if col_idx.get("jockey_name") is not None else None
    trainer_cell = cells[col_idx.get("trainer_name", -1)] if col_idx.get("trainer_name") is not None else None

    if horse_cell:
        a = horse_cell.find("a", href=True)
        if a:
            e["horse_id"] = _id_from_href(a["href"], _ID_HORSE_RE)
    if jockey_cell:
        a = jockey_cell.find("a", href=True)
        if a:
            e["jockey_id"] = _id_from_href(a["href"], _ID_JOCKEY_RE)
    if trainer_cell:
        a = trainer_cell.find("a", href=True)
        if a:
            e["trainer_id"] = _id_from_href(a["href"], _ID_TRAINER_RE)

    return e
