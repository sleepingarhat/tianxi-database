"""Trainer profile + records parser.

Fixes Replit's D1 bug (TrainerData_Scraper.py silently failed on SPA ranking page).
Strategy: we scrape /local/information/trainerprofile?trainerid=CODE (SSR) directly.
IDs come from the weekly Playwright scrape of the ranking SPA.
"""
from __future__ import annotations

import logging
import re
from typing import Any

from ..shared.utils import clean_text, normalize_date, safe_cell, soup

logger = logging.getLogger(__name__)

# Stable CSV schema for trainer RECORDS (per-race history)
# Different from Replit's dynamic schema — we pin these column names.
TRAINER_RECORD_COLS: list[str] = [
    "trainer_id",
    "trainer_name",
    "season",
    "date",
    "venue",
    "race_no",
    "horse_no",
    "horse_name",
    "jockey",
    "place",
    "weight_carried_lbs",
    "draw",
    "lbw",
    "win_odds",
    "distance_m",
    "going",
    "track",
    "race_class",
]

# Trainer PROFILE master CSV columns (single-row-per-trainer summary)
TRAINER_PROFILE_COLS: list[str] = [
    "trainer_id",
    "trainer_name",
    "season",
    "total_starts",
    "wins",
    "2nd",
    "3rd",
    "4th",
    "5th",
    "win_rate_pct",
    "place_rate_pct",
    "total_stakes_hkd",
    "stable_location",
    "profile_last_scraped",
]


# ---------- Profile page parser ----------


def parse_profile(html: str, trainer_id: str) -> dict[str, Any] | None:
    """Parse /zh-hk/local/information/trainerprofile?trainerid=XX page.

    Returns dict matching TRAINER_PROFILE_COLS (or None if invalid trainer / 404).
    """
    s = soup(html)
    # Invalid trainer detection: HKJC shows 沒有相關資料 / redirects to index
    body_text = s.get_text(" ", strip=True)
    if "沒有相關資料" in body_text or len(body_text) < 200:
        logger.info("Trainer %s: no data marker found", trainer_id)
        return None

    # Trainer name: usually in h1/h2 or specific element
    name = _extract_trainer_name(s)
    if not name:
        logger.warning("Trainer %s: could not extract name", trainer_id)
        return None

    stats = _extract_stats_block(s)

    profile: dict[str, Any] = {
        "trainer_id": trainer_id,
        "trainer_name": name,
        "season": stats.get("season", ""),
        "total_starts": stats.get("total_starts", ""),
        "wins": stats.get("wins", ""),
        "2nd": stats.get("2nd", ""),
        "3rd": stats.get("3rd", ""),
        "4th": stats.get("4th", ""),
        "5th": stats.get("5th", ""),
        "win_rate_pct": stats.get("win_rate_pct", ""),
        "place_rate_pct": stats.get("place_rate_pct", ""),
        "total_stakes_hkd": stats.get("total_stakes_hkd", ""),
        "stable_location": stats.get("stable_location", ""),
        "profile_last_scraped": "",  # filled by orchestrator
    }
    return profile


def _extract_trainer_name(s) -> str:
    """Try multiple heuristics to find trainer Chinese name."""
    # HKJC trainer profile page: 練馬師簡介 - 姓名 in a prominent header
    for selector in ["h1", "h2", ".f_fs18", ".profile-name", ".trainer-name"]:
        for el in s.select(selector):
            text = clean_text(el.get_text(" "))
            # Drop very long titles
            if 1 < len(text) < 40 and "練馬師" not in text:
                return text
    # Fallback: look for pattern like "姓名 : XXX" in table
    for td in s.find_all(["td", "dt"]):
        label = clean_text(td.get_text(" "))
        if label in ("姓名", "練馬師姓名", "Name"):
            nxt = td.find_next_sibling(["td", "dd"])
            if nxt:
                return clean_text(nxt.get_text(" "))
    return ""


def _extract_stats_block(s) -> dict[str, str]:
    """Find stats table: season / total / wins / 2nd / 3rd / 4th / 5th / win_rate / stakes."""
    stats: dict[str, str] = {}
    # Look for table with headers 出賽次數 / 頭馬 / 亞軍 etc.
    for table in s.find_all("table"):
        headers = [clean_text(h.get_text(" ")) for h in table.find_all(["th", "td"], limit=12)]
        header_text = " ".join(headers)
        if "頭馬" in header_text and "亞軍" in header_text:
            rows = table.find_all("tr")
            if len(rows) >= 2:
                data_cells = rows[1].find_all(["td", "th"])
                values = [clean_text(c.get_text(" ")) for c in data_cells]
                # Typical order: 出賽次數 頭馬 亞軍 季軍 第四名 第五名 獎金
                if len(values) >= 6:
                    stats["total_starts"] = values[0]
                    stats["wins"] = values[1]
                    stats["2nd"] = values[2]
                    stats["3rd"] = values[3]
                    stats["4th"] = values[4]
                    stats["5th"] = values[5]
                    if len(values) >= 7:
                        stats["total_stakes_hkd"] = re.sub(r"[^\d.]", "", values[6])
            break

    # Season: look for "2024/25", "2025/26" pattern
    body_text = s.get_text(" ", strip=True)
    m = re.search(r"(20\d{2}\s*/\s*\d{2})", body_text)
    if m:
        stats["season"] = m.group(1).replace(" ", "")

    # Win rate
    m = re.search(r"勝率[:\s]*([\d.]+)\s*%", body_text)
    if m:
        stats["win_rate_pct"] = m.group(1)
    m = re.search(r"上名率[:\s]*([\d.]+)\s*%", body_text)
    if m:
        stats["place_rate_pct"] = m.group(1)

    return stats


# ---------- Records table parser ----------


def parse_records(html: str, trainer_id: str, trainer_name: str, season: str) -> list[dict[str, Any]]:
    """
    Parse trainer past record table.

    Real HKJC structure (TrainerPastRec.aspx):
      - One header row (14 columns)
      - Alternating single-cell DATE+VENUE rows (e.g. "22/04/2026  跑馬地")
        and multi-cell DATA rows (16 cells, where the last 3 cells are the
        first-three-finishers expansion of the "首三名馬匹" header slot).

    Columns in header:
      場次 | 馬匹 | 名次 | 跑道/賽道 | 途程 | 場地狀況 | 檔位 | 評分 | 賠率 | 騎師 | 配備 | 馬匹體重 | 實際負磅 | 首三名馬匹
      idx: 0     1      2       3          4      5         6     7      8      9      10     11        12         13(+14,15)
    """
    import re as _re
    from ..shared.utils import extract_horse_no

    s = soup(html)
    out: list[dict[str, Any]] = []

    target_table = None
    for table in s.find_all("table"):
        cls = table.get("class") or []
        if "table_bd" not in cls:
            continue
        header_cells = table.find_all(["th", "td"], limit=20)
        header_text = " ".join(clean_text(c.get_text(" ")) for c in header_cells)
        if "馬匹" in header_text and "場" in header_text and "名次" in header_text:
            target_table = table
            break
    if target_table is None:
        logger.info("Trainer %s records: no records table found", trainer_id)
        return out

    # Regex for date section headers: "22/04/2026  跑馬地"
    date_hdr_re = _re.compile(r"(\d{1,2}/\d{1,2}/\d{2,4})\s*[\u00a0\s]*(沙田|跑馬地)?")

    current_date = ""
    current_venue = ""

    for tr in target_table.find_all("tr")[1:]:  # skip header
        cells = tr.find_all(["td", "th"])
        if len(cells) == 1:
            txt = clean_text(cells[0].get_text(" ", strip=True)).replace("\xa0", " ")
            m = date_hdr_re.search(txt)
            if m:
                current_date = normalize_date(m.group(1))
                current_venue = m.group(2) or ""
            continue
        if len(cells) < 13:
            continue

        vals = [clean_text(c.get_text(" ", strip=True)) for c in cells]

        # Split 跑道/賽道 into track + course
        track_raw = vals[3]
        track = ""
        course = ""
        tm = _re.match(
            r'(草地|全天候|泥地)(?:\s*"?\s*([A-Z0-9+]+)\s*"?\s*)?',
            track_raw.replace("\xa0", " "),
        )
        if tm:
            track = tm.group(1)
            course = tm.group(2) or ""
        if not course:
            # try ASCII quotes
            q = _re.search(r'"([A-Z0-9+]+)"', track_raw)
            if q:
                course = q.group(1)

        place_raw = vals[2]  # e.g. "2/12"
        place = place_raw.split("/")[0].strip() if place_raw else ""

        row: dict[str, Any] = {
            "trainer_id": trainer_id,
            "trainer_name": trainer_name,
            "season": season,
            "date": current_date,
            "venue": current_venue,
            "race_no": vals[0],
            "horse_no": extract_horse_no(vals[1]),
            "horse_name": vals[1],
            "jockey": vals[9] if len(vals) > 9 else "",
            "place": place,
            "weight_carried_lbs": vals[12] if len(vals) > 12 else "",
            "draw": vals[6] if len(vals) > 6 else "",
            "lbw": "",  # HKJC trainer page has no headwinner-distance column
            "win_odds": vals[8] if len(vals) > 8 else "",
            "distance_m": vals[4] if len(vals) > 4 else "",
            "going": vals[5] if len(vals) > 5 else "",
            "track": track,
            "race_class": "",  # Not shown in trainer past rec table
        }
        if not row["date"] and not row["horse_name"]:
            continue
        out.append(row)

    return out


# Map Chinese header text → logical column key
_HEADER_MAP = {
    "日期": "date",
    "場地": "venue",
    "馬場": "venue",
    "場次": "race_no",
    "馬匹": "horse_name",
    "馬名": "horse_name",
    "騎師": "jockey",
    "名次": "place",
    "評分": "rating",
    "負磅": "weight_carried_lbs",
    "實際負磅": "weight_carried_lbs",
    "檔位": "draw",
    "檔": "draw",
    "頭馬距離": "lbw",
    "距離": "distance_m",
    "途程": "distance_m",
    "場地情況": "going",
    "跑道": "track",
    "班次": "race_class",
    "獨贏賠率": "win_odds",
    "獨贏": "win_odds",
}


def _build_column_index(headers: list[str]) -> dict[str, int]:
    idx: dict[str, int] = {}
    for i, h in enumerate(headers):
        for k, v in _HEADER_MAP.items():
            if k in h:
                idx[v] = i
                break
    return idx
