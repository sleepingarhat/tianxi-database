"""Utility functions ported from Replit scraper_utils.py.

Kept 1:1 behaviour-compatible where possible so CSV outputs match byte-for-byte.
"""
from __future__ import annotations

import logging
import re
from typing import Iterable

from bs4 import BeautifulSoup, Tag

logger = logging.getLogger(__name__)

# ============ Text cleaning ============

_WHITESPACE = re.compile(r"\s+")


def clean_text(value: str | None) -> str:
    """Normalise whitespace, strip. Empty string for None."""
    if value is None:
        return ""
    return _WHITESPACE.sub(" ", value).strip()


def safe_cell(cells: list[Tag] | list[str], idx: int, default: str = "") -> str:
    """Return cleaned text of cell[idx] or default. Matches Replit safe_cell."""
    try:
        cell = cells[idx]
        if isinstance(cell, Tag):
            return clean_text(cell.get_text(separator=" "))
        return clean_text(str(cell))
    except (IndexError, TypeError):
        return default


# ============ Horse name parsing ============

_HORSE_NO_RE = re.compile(r"\(([A-Z]\d{3,4})\)")
_RETIRED_MARKER = re.compile(r"\s*\(已退役\)\s*$")


def extract_horse_no(name_cell: str) -> str:
    """Extract HKJC horse_no (e.g. 'A001', 'S246') from cell text like 'DOUBLE POINT (S246)'."""
    m = _HORSE_NO_RE.search(name_cell or "")
    return m.group(1) if m else ""


def strip_horse_no(name_cell: str) -> str:
    """Remove (horse_no) and (已退役) markers, return pure horse name."""
    s = _HORSE_NO_RE.sub("", name_cell or "")
    s = _RETIRED_MARKER.sub("", s)
    return clean_text(s)


def is_retired(name_cell: str) -> bool:
    return bool(_RETIRED_MARKER.search(name_cell or ""))


# ============ Location parsing ============

# HKJC venue codes used in results URLs / data
VENUE_ZH_TO_CODE = {
    "沙田": "ST",
    "跑馬地": "HV",
}


def parse_zh_location(text: str) -> tuple[str, str, str]:
    """
    Parse strings like:
      '沙田 草地"A"' → ('ST', '草地', 'A')
      '跑馬地 全天候跑道' → ('HV', '全天候跑道', '')
      '沙田 草地"C"' → ('ST', '草地', 'C')
      '沙田 全天候跑道' → ('ST', '全天候跑道', '')
    Returns (venue_code, track, course).
    """
    if not text:
        return ("", "", "")
    s = clean_text(text)
    # venue
    venue = ""
    for zh, code in VENUE_ZH_TO_CODE.items():
        if s.startswith(zh):
            venue = code
            s = s[len(zh):].strip()
            break
    # course letter in quotes
    course = ""
    m = re.search(r'[""]([A-Z0-9]+)[""]', s)
    if m:
        course = m.group(1)
        s = re.sub(r'[""][A-Z0-9]+[""]', "", s).strip()
    # also handle ASCII quotes
    m = re.search(r'"([A-Z0-9]+)"', s)
    if m and not course:
        course = m.group(1)
        s = re.sub(r'"[A-Z0-9]+"', "", s).strip()
    track = clean_text(s)
    return (venue, track, course)


# ============ Date parsing ============

DATE_SLASH_RE = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")  # DD/MM/YYYY
DATE_DASH_RE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")  # YYYY-MM-DD


def normalize_date(s: str) -> str:
    """Return ISO YYYY-MM-DD from various HKJC date formats."""
    s = (s or "").strip()
    m = DATE_DASH_RE.match(s)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    m = DATE_SLASH_RE.match(s)
    if m:
        d, mo, y = m.group(1), m.group(2), m.group(3)
        return f"{y}-{int(mo):02d}-{int(d):02d}"
    return ""


def hkjc_date_slash(iso: str) -> str:
    """'2026-04-22' → '22/04/2026' (Replit URL format)."""
    m = DATE_DASH_RE.match(iso or "")
    if not m:
        return ""
    return f"{m.group(3)}/{m.group(2)}/{m.group(1)}"


def hkjc_date_yyyymmdd(iso: str) -> str:
    """'2026-04-22' → '20260422' (trials URL format)."""
    m = DATE_DASH_RE.match(iso or "")
    if not m:
        return ""
    return f"{m.group(1)}{m.group(2)}{m.group(3)}"


# ============ HTML helpers ============


def soup(html: str) -> BeautifulSoup:
    """Canonical BeautifulSoup factory — prefer lxml, fallback html.parser."""
    try:
        return BeautifulSoup(html, "lxml")
    except Exception:
        return BeautifulSoup(html, "html.parser")


def find_data_table(soup_: BeautifulSoup, *, header_contains: Iterable[str]) -> Tag | None:
    """Find first <table> whose header row contains ANY of the given terms."""
    terms = [t.strip() for t in header_contains if t]
    for table in soup_.find_all("table"):
        header_cells = table.find_all(["th", "td"], limit=40)
        header_text = " ".join(cell.get_text(" ", strip=True) for cell in header_cells)
        if any(term in header_text for term in terms):
            return table
    return None


# ============ Numeric parsing ============


def to_int(s: str | None, default: int = 0) -> int:
    if s is None:
        return default
    m = re.search(r"-?\d+", str(s))
    return int(m.group(0)) if m else default


def to_float(s: str | None, default: float | None = None) -> float | None:
    if s is None:
        return default
    m = re.search(r"-?\d+(\.\d+)?", str(s))
    return float(m.group(0)) if m else default
