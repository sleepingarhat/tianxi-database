"""
Horse profile parser — `Horse.aspx?HorseNo=XXX` SSR HTML.

Single URL serves BOTH the profile key-value block AND the form records
table. This parser extracts only the profile. See `horse_form.py` for the
history table.

Pinned column schema matches Replit `horses/profiles/horse_profiles.csv`
EXACTLY (16 cols, including the Chinese field names and the '毛色___性別'
triple-underscore convention for slash-safe CSV header).
"""
from __future__ import annotations

import datetime as _dt
import re
from typing import Any

from bs4 import BeautifulSoup, Tag

from ..shared.utils import clean_text, soup as _soup

# ---------------------------------------------------------------------------
# Pinned 16-column schema (matches Replit horse_profiles.csv)
# ---------------------------------------------------------------------------

PROFILE_COLS: list[str] = [
    "horse_no",
    "name",
    "last_race_date",
    "status",
    "profile_last_scraped",
    "出生地",
    "毛色___性別",          # slash normalized to triple underscore
    "進口類別",
    "總獎金",
    "冠-亞-季-總出賽次數",
    "馬主",
    "最後評分",
    "父系",
    "母系",
    "外祖父",
    "同父系馬",
]

# Fields we read directly from the key-value block
# (key text -> target column in the pinned schema)
_KEY_TO_COL: dict[str, str] = {
    "出生地 / 馬齡": "出生地",           # keep left part only, strip age
    "毛色 / 性別": "毛色___性別",
    "進口類別": "進口類別",
    "總獎金*": "總獎金",
    "總獎金": "總獎金",
    "冠-亞-季-總出賽次數*": "冠-亞-季-總出賽次數",
    "冠-亞-季-總出賽次數": "冠-亞-季-總出賽次數",
    "馬主": "馬主",
    "現時評分": "最後評分",
    "父系": "父系",
    "母系": "母系",
    "外祖父": "外祖父",
    "同父系馬": "同父系馬",
}

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def parse_profile(html: str, horse_no: str) -> dict[str, Any] | None:
    """Return one profile row dict (keys = PROFILE_COLS), or None if no data."""
    soup = _soup(html)

    # Find the main horseProfile table
    main = _find_main_table(soup)
    if main is None:
        return None

    name, status = _extract_name_and_status(soup, horse_no)
    if not name:
        # Profile page with no horse data (phantom / archived)
        return None

    kv = _extract_kv_pairs(main)
    row: dict[str, Any] = {c: "" for c in PROFILE_COLS}
    row["horse_no"] = horse_no.strip().upper()
    row["name"] = name
    row["status"] = status
    row["profile_last_scraped"] = _dt.date.today().isoformat()

    # Copy mapped fields
    for zh_key, val in kv.items():
        col = _KEY_TO_COL.get(zh_key)
        if not col:
            continue
        if col == "出生地":
            # "澳洲 / 5" → "澳洲"
            row[col] = val.split("/")[0].strip()
        elif col == "毛色___性別":
            # Keep "栗 / 閹" verbatim per Replit convention
            row[col] = val
        else:
            row[col] = val

    # last_race_date — pulled from first form_records data row (orchestrator fills)
    # If we can find it inline, do so as fallback.
    row["last_race_date"] = _extract_last_race_date(soup)

    return row


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _find_main_table(soup: BeautifulSoup) -> Tag | None:
    for t in soup.find_all("table"):
        cls = t.get("class") or []
        if "horseProfile" in cls:
            return t
    return None


_NAME_WITH_BRAND_RE = re.compile(r"^(.+?)\s*\(([A-Z0-9]+)\)(.*)$")
_RETIRED_RE = re.compile(r"\(已退役\)")


def _extract_name_and_status(soup: BeautifulSoup, horse_no: str) -> tuple[str, str]:
    """
    HKJC renders the full name with brand and retired suffix inside a span
    near the top of the profile, e.g. '志滿同行 (K056)' or '福穎 (A001) (已退役)'.
    We keep the full string verbatim for `name` and set `status` from the retired flag.
    """
    # First look for a span/heading that contains the brand code in parens
    target = (horse_no or "").strip().upper()
    for sel in ["span.horseName", "h1", "h2", "td"]:
        for el in soup.select(sel):
            txt = clean_text(el.get_text(" ", strip=True))
            if not txt:
                continue
            if target and f"({target})" in txt and len(txt) < 60:
                status = "retired" if _RETIRED_RE.search(txt) else "active"
                return txt, status

    # Fallback: <title> tag — HKJC format "<name> - 馬匹資料 - ..."
    title = soup.find("title")
    if title:
        t = clean_text(title.get_text())
        # strip " - 馬匹資料 - 賽馬資訊 - 香港賽馬會"
        t = re.sub(r"\s*-\s*馬匹資料.*$", "", t)
        if t:
            status = "retired" if _RETIRED_RE.search(t) else "active"
            if target and f"({target})" not in t:
                t = f"{t} ({target})"
            return t, status
    return "", ""


def _extract_kv_pairs(table: Tag) -> dict[str, str]:
    """
    Key-value pairs appear in 3-column rows: [label, ':', value].
    Some rows span multiple pairs in a single <tr>; we walk cell-by-cell.
    """
    out: dict[str, str] = {}
    cells = [clean_text(td.get_text(" ", strip=True)) for td in table.find_all("td")]

    # Scan for "label ':' value" triplets
    i = 0
    while i < len(cells) - 2:
        if cells[i + 1] == ":" and cells[i]:
            key = cells[i]
            val = cells[i + 2]
            if key not in out:
                out[key] = val
            i += 3
        else:
            i += 1
    return out


def _extract_last_race_date(soup: BeautifulSoup) -> str:
    """First data row of the form-records table has the most recent race date."""
    form_table = None
    for t in soup.find_all("table"):
        cls = t.get("class") or []
        if "bigborder" in cls:
            form_table = t
            break
    if form_table is None:
        return ""
    rows = form_table.find_all("tr")
    for tr in rows[1:]:
        cells = tr.find_all("td")
        if len(cells) < 3:
            continue  # season header row
        date_cell = clean_text(cells[2].get_text(" ", strip=True))
        # Format: DD/MM/YY → DD/MM/YYYY → ISO YYYY-MM-DD
        m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{2,4})", date_cell)
        if m:
            dd, mm, yy = m.group(1), m.group(2), m.group(3)
            year = int(yy)
            if year < 100:
                year = 2000 + year if year < 50 else 1900 + year
            try:
                d = _dt.date(year, int(mm), int(dd))
                return d.isoformat()
            except ValueError:
                return ""
    return ""
