"""
Race results parser — `LocalResults.aspx` SSR HTML.

Source URL pattern:
    https://racing.hkjc.com/racing/information/Chinese/racing/LocalResults.aspx
      ?RaceDate=DD/MM/YYYY&Racecourse=ST|HV&RaceNo=<n>

Produces FIVE CSV-ready row lists matching Replit's exact schemas so existing
downstream Elo/consumer code continues to work byte-identical:

  - results        (25 cols)  one row per horse
  - sectional_times(25 cols)  one row per horse, six sector slots
  - commentary     ( 9 cols)  one row per horse
  - dividends      ( 6 cols)  one row per pool×combination
  - video_links    ( 6 cols)  one row per race

Column order is PINNED. Layout-change detection: if the expected table is
missing or the header row does not contain all mandatory Chinese markers,
the parser raises ValueError rather than silently emitting empty rows.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import quote

from bs4 import BeautifulSoup, Tag

from ..shared.utils import clean_text, soup as _soup, to_float, to_int

# ---------------------------------------------------------------------------
# Pinned column schemas (order matches Replit CSV output exactly)
# ---------------------------------------------------------------------------

RESULT_COLS: list[str] = [
    "date", "venue", "race_no", "race_meeting_no", "race_name",
    "race_class", "distance_m", "rating_range", "going", "course",
    "prize_hkd", "race_finish_time", "sectional_times_header",
    "place", "horse_no", "horse_name", "jockey", "trainer",
    "actual_wt_lbs", "declared_wt_lbs", "draw", "lbw",
    "running_position", "finish_time", "win_odds",
]

SECTIONAL_COLS: list[str] = [
    "date", "venue", "race_no", "finish_pos", "horse_no", "horse_name",
    "finish_time",
    "sec1_margin", "sec1_running_pos", "sec1_time",
    "sec2_margin", "sec2_running_pos", "sec2_time",
    "sec3_margin", "sec3_running_pos", "sec3_time",
    "sec4_margin", "sec4_running_pos", "sec4_time",
    "sec5_margin", "sec5_running_pos", "sec5_time",
    "sec6_margin", "sec6_running_pos", "sec6_time",
]

COMMENTARY_COLS: list[str] = [
    "date", "venue", "race_no", "place", "horse_no", "horse_name",
    "jockey", "gear", "commentary",
]

DIVIDEND_COLS: list[str] = [
    "date", "venue", "race_no", "pool", "combination", "dividend_hkd",
]

VIDEO_COLS: list[str] = [
    "date", "venue", "race_no",
    "video_full_url", "video_passthrough_url", "video_aerial_url",
]

# ---------------------------------------------------------------------------
# Regexes for parsing the race-info block
# ---------------------------------------------------------------------------

_RACE_NO_RE = re.compile(r"第\s*(\d+)\s*場")
_MEETING_NO_RE = re.compile(r"第\s*\d+\s*場\s*\(?(\d+)\)?")
_CLASS_DIST_RATING_RE = re.compile(
    r"(第[一二三四五六七八九十]+班|國際[一二三四五]+級|[^|]*?賽事)\s*-\s*"
    r"(\d{3,4})\s*米\s*-\s*\(?([\d\-]+)\)?"
)
_COURSE_LINE_RE = re.compile(r"(草地|全天候).*?賽道")
_PRIZE_RE = re.compile(r"HK\$\s*([\d,]+)")


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------


@dataclass
class RaceResultsParse:
    results: list[dict[str, Any]] = field(default_factory=list)
    sectional_times: list[dict[str, Any]] = field(default_factory=list)
    commentary: list[dict[str, Any]] = field(default_factory=list)
    dividends: list[dict[str, Any]] = field(default_factory=list)
    video_links: list[dict[str, Any]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def parse_race_results(
    html: str,
    *,
    race_date_iso: str,
    venue_zh: str,
    race_no: int,
) -> RaceResultsParse:
    """Parse one LocalResults page. All five tables in one pass."""
    soup = _soup(html)
    base = {"date": race_date_iso, "venue": venue_zh, "race_no": race_no}

    meta = _parse_race_info(soup)
    result_rows = _parse_result_table(soup, base, meta)
    sec_rows = _parse_sectional_rows(soup, base, result_rows)
    comm_rows = _parse_commentary(soup, base)
    div_rows = _parse_dividends(soup, base)
    video_rows = [_build_video_row(base)]

    return RaceResultsParse(
        results=result_rows,
        sectional_times=sec_rows,
        commentary=comm_rows,
        dividends=div_rows,
        video_links=video_rows,
    )


# ---------------------------------------------------------------------------
# Race info block (table 1)
# ---------------------------------------------------------------------------


def _parse_race_info(soup: BeautifulSoup) -> dict[str, Any]:
    """Extract race name, class, distance, rating, course, prize, time, sectionals."""
    meta: dict[str, Any] = {
        "race_meeting_no": None,
        "race_name": "",
        "race_class": "",
        "distance_m": None,
        "rating_range": "",
        "going": "",
        "course": "",
        "prize_hkd": None,
        "race_finish_time": "",
        "sectional_times_header": "",
    }

    # Find the race-info table (not the starter table and not the dividends table)
    info_table = None
    for t in soup.find_all("table"):
        txt = t.get_text(" ", strip=True)
        if "場地狀況" in txt and "賽道" in txt and "時間" in txt:
            info_table = t
            break
    if info_table is None:
        raise ValueError("race-info table not found (missing 場地狀況/賽道/時間 markers)")

    # Collect all cell texts in order
    cells = [clean_text(td.get_text(" ", strip=True)) for td in info_table.find_all(["th", "td"])]
    joined = " | ".join(cells)

    # race_meeting_no
    m = _MEETING_NO_RE.search(joined)
    if m:
        meta["race_meeting_no"] = to_int(m.group(1))

    # class + distance + rating
    m = _CLASS_DIST_RATING_RE.search(joined)
    if m:
        meta["race_class"] = m.group(1).strip()
        meta["distance_m"] = to_int(m.group(2))
        meta["rating_range"] = m.group(3).strip()

    # going — cell AFTER "場地狀況 :"
    for i, c in enumerate(cells):
        if "場地狀況" in c and i + 1 < len(cells):
            meta["going"] = cells[i + 1]
            break

    # course — full string e.g. '草地 - "B" 賽道'
    for c in cells:
        if "賽道" in c and ("草地" in c or "全天候" in c) and "場地狀況" not in c:
            meta["course"] = c
            break

    # race_name — cell that's none of the above and not a label
    # Heuristic: between "場地狀況/going" and "賽道 :/course"
    # Replit produces just the plain name, so pick the cell that has no colon and no digit-only content.
    for i, c in enumerate(cells):
        if not c or ":" in c or "場" in c or "班" in c or "米" in c or "賽道" in c:
            continue
        if "場地狀況" in c or "時間" in c or "分段時間" in c or c.startswith("HK$"):
            continue
        # Skip cells that are just numbers/times
        if re.match(r"^[\d:.()\-\s]+$", c):
            continue
        if "好" in c or "快" in c or "軟" in c or "黏" in c or "濕" in c or "大爛" in c:
            # Going word, not name
            continue
        if len(c) <= 2:
            continue
        meta["race_name"] = c
        break

    # prize
    m = _PRIZE_RE.search(joined)
    if m:
        meta["prize_hkd"] = to_int(m.group(1).replace(",", ""))

    # race_finish_time — all the (time) cells concatenated e.g. "(23.70) (46.11) (1:09.33)"
    times = [c for c in cells if re.match(r"^\(\d+[:.]?\d*[.:]?\d*\)$", c)]
    if times:
        meta["race_finish_time"] = " ".join(times)

    # sectional_times_header — cells between "分段時間 :" and the next label
    try:
        idx = next(i for i, c in enumerate(cells) if "分段時間" in c)
    except StopIteration:
        idx = -1
    if idx >= 0:
        buf: list[str] = []
        for c in cells[idx + 1:]:
            if not c or ":" in c:
                break
            if re.match(r"^[\d.\s]+$", c.replace("\xa0", " ")):
                buf.append(c)
            else:
                break
        if buf:
            # Replit joins first-sector values with spaces, replaces nbsp→space
            cleaned = [re.sub(r"\s+", " ", c.replace("\xa0", " ")).strip() for c in buf]
            meta["sectional_times_header"] = " ".join(cleaned)

    return meta


# ---------------------------------------------------------------------------
# Result table (12 cols)
# ---------------------------------------------------------------------------


_RESULT_HEADERS_REQUIRED = ["名次", "馬號", "馬名", "騎師", "練馬師"]


def _find_result_table(soup: BeautifulSoup) -> Tag:
    for t in soup.find_all("table"):
        first_row = t.find("tr")
        if not first_row:
            continue
        hdr = " ".join(c.get_text(" ", strip=True) for c in first_row.find_all(["th", "td"]))
        if all(h in hdr for h in _RESULT_HEADERS_REQUIRED):
            return t
    raise ValueError("result table not found (missing required 名次/馬號/馬名/騎師/練馬師)")


def _parse_result_table(
    soup: BeautifulSoup,
    base: dict[str, Any],
    meta: dict[str, Any],
) -> list[dict[str, Any]]:
    table = _find_result_table(soup)
    rows = table.find_all("tr")
    if len(rows) < 2:
        return []

    out: list[dict[str, Any]] = []
    for tr in rows[1:]:
        cells = tr.find_all("td")
        if len(cells) < 12:
            continue
        vals = [clean_text(c.get_text(" ", strip=True)) for c in cells]
        row: dict[str, Any] = {c: "" for c in RESULT_COLS}
        row.update(base)
        row.update(meta)
        row["place"] = vals[0]
        row["horse_no"] = vals[1]
        row["horse_name"] = vals[2]
        row["jockey"] = vals[3]
        row["trainer"] = vals[4]
        row["actual_wt_lbs"] = to_int(vals[5]) if vals[5] else None
        row["declared_wt_lbs"] = to_int(vals[6]) if vals[6] else None
        row["draw"] = to_int(vals[7]) if vals[7] else None
        row["lbw"] = vals[8]
        row["running_position"] = vals[9]
        row["finish_time"] = vals[10]
        row["win_odds"] = vals[11]
        out.append(row)
    return out


# ---------------------------------------------------------------------------
# Sectional times (from the separate sectional-times page or result table)
# ---------------------------------------------------------------------------


def _parse_sectional_rows(
    soup: BeautifulSoup,
    base: dict[str, Any],
    result_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    LocalResults.aspx contains the running positions (e.g. "1 1 1") in the
    main table. Detailed sectional margins/times live on a *different* page
    (Sectional_Time.aspx). We emit a stub row per horse filled from result_rows
    so the downstream CSV has one row per horse even before the orchestrator
    fetches the dedicated sectional page.

    Orchestrator later replaces stubs with full sectional data.
    """
    out: list[dict[str, Any]] = []
    for r in result_rows:
        row: dict[str, Any] = {c: "" for c in SECTIONAL_COLS}
        row.update(base)
        row["finish_pos"] = r["place"]
        row["horse_no"] = r["horse_no"]
        row["horse_name"] = r["horse_name"]
        row["finish_time"] = r["finish_time"]
        out.append(row)
    return out


# ---------------------------------------------------------------------------
# Commentary (stewards' events)
# ---------------------------------------------------------------------------


def _find_commentary_table(soup: BeautifulSoup) -> Tag | None:
    for t in soup.find_all("table"):
        first_row = t.find("tr")
        if not first_row:
            continue
        hdr = " ".join(c.get_text(" ", strip=True) for c in first_row.find_all(["th", "td"]))
        if "競賽事件" in hdr and "馬名" in hdr:
            return t
    return None


def _parse_commentary(soup: BeautifulSoup, base: dict[str, Any]) -> list[dict[str, Any]]:
    table = _find_commentary_table(soup)
    if table is None:
        return []
    rows = table.find_all("tr")
    out: list[dict[str, Any]] = []
    for tr in rows[1:]:
        cells = tr.find_all("td")
        if len(cells) < 4:
            continue
        vals = [clean_text(c.get_text(" ", strip=True)) for c in cells]
        row = {c: "" for c in COMMENTARY_COLS}
        row.update(base)
        row["place"] = vals[0]
        row["horse_no"] = vals[1]
        row["horse_name"] = vals[2]
        # Replit CSV has `jockey` + `gear` columns, which the HKJC commentary
        # table does NOT provide directly. Orchestrator joins from result_rows.
        row["commentary"] = vals[3] if len(vals) == 4 else " ".join(vals[3:])
        out.append(row)
    return out


# ---------------------------------------------------------------------------
# Dividends (派彩)
# ---------------------------------------------------------------------------


def _find_dividends_table(soup: BeautifulSoup) -> Tag | None:
    for t in soup.find_all("table"):
        txt = t.get_text(" ", strip=True)
        if "派彩" in txt and "彩池" in txt:
            return t
    return None


# HKJC pool labels
_POOL_LABELS = {
    "獨贏", "位置", "連贏", "位置Q", "單T", "孖寶", "三重彩", "孖T",
    "六環彩", "四連環", "三T", "四重彩", "孖寶", "四寶", "四連環",
    "五重彩", "六連環",
}


def _parse_dividends(soup: BeautifulSoup, base: dict[str, Any]) -> list[dict[str, Any]]:
    table = _find_dividends_table(soup)
    if table is None:
        return []
    rows = table.find_all("tr")
    out: list[dict[str, Any]] = []
    current_pool = ""
    for tr in rows:
        cells = tr.find_all(["th", "td"])
        vals = [clean_text(c.get_text(" ", strip=True)) for c in cells]
        if not vals:
            continue
        # Header rows
        if any(v in {"派彩", "彩池", "勝出組合", "派彩 (HK$)"} for v in vals):
            continue

        # 3-column row: pool, combination, dividend
        if len(vals) >= 3 and _looks_like_pool(vals[0]):
            current_pool = vals[0]
            row = {c: "" for c in DIVIDEND_COLS}
            row.update(base)
            row["pool"] = current_pool
            row["combination"] = vals[1]
            row["dividend_hkd"] = _money(vals[2])
            out.append(row)
        # 2-column continuation row: combination, dividend (inherits pool)
        elif len(vals) == 2 and current_pool:
            row = {c: "" for c in DIVIDEND_COLS}
            row.update(base)
            row["pool"] = current_pool
            row["combination"] = vals[0]
            row["dividend_hkd"] = _money(vals[1])
            out.append(row)
    return out


def _looks_like_pool(v: str) -> bool:
    if not v:
        return False
    # Exact match against known labels OR contains one
    return any(label in v for label in _POOL_LABELS)


def _money(s: str) -> float | None:
    s = (s or "").replace(",", "").replace("$", "").strip()
    if not s or s in {"-", "N/A"}:
        return None
    try:
        return float(s)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Video links
# ---------------------------------------------------------------------------


def _build_video_row(base: dict[str, Any]) -> dict[str, Any]:
    """
    HKJC exposes three replay video types via a stable URL template:
      type=replay-full        — full race replay
      type=passthrough        — passthrough view
      type=replay-aerial      — aerial view
    All three URLs follow the same template, just differ by `type` param.
    """
    date_compact = base["date"].replace("-", "")  # 2026-04-22 → 20260422
    race_no = f"{int(base['race_no']):02d}"
    rf = (
        f"http://racing.hkjc.com/zh-hk/local/information/localresults"
        f"?racedate={base['date'].replace('-', '/')}&racecourse=&raceno={base['race_no']}"
        f"&pageid=racing/local"
    )
    template = (
        "https://racing.hkjc.com/contentAsset/videoplayer_v4/"
        "video-player-iframe_v4.html?type={t}&date={d}&no={n}&lang=chi"
        "{extra}&videoParam=PA&rf={rf}"
    )

    def url(t: str, extra: str = "") -> str:
        return template.format(t=t, d=date_compact, n=race_no, rf=rf, extra=extra)

    row = {c: "" for c in VIDEO_COLS}
    row.update(base)
    row["video_full_url"] = url("replay-full", "&noPTbar=false&noLeading=false")
    row["video_passthrough_url"] = url("passthrough")
    row["video_aerial_url"] = url("replay-aerial")
    return row
