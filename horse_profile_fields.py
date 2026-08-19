"""Canonical parsing and safe merging for HKJC public horse profiles."""

from __future__ import annotations

import math
import re
import unicodedata
from html.parser import HTMLParser
from typing import Iterable, Mapping


PROFILE_PARSER_VERSION = "hkjc-labels-v2"
PROFILE_SOURCE_KIND = "HKJC public horse profile"
PROFILE_SOURCE_URL = (
    "https://racing.hkjc.com/racing/information/Chinese/Horse/"
    "Horse.aspx?HorseNo={horse_no}"
)

CANONICAL_PROFILE_FIELDS = (
    "出生地",
    "毛色___性別",
    "進口類別",
    "今季獎金",
    "總獎金",
    "冠-亞-季-總出賽次數",
    "練馬師",
    "馬主",
    "最後評分",
    "父系",
    "母系",
    "外祖父",
    "同父系馬",
)

PROFILE_COVERAGE_FIELDS = (
    "出生地",
    "毛色___性別",
    "進口類別",
    "今季獎金",
    "總獎金",
    "練馬師",
    "馬主",
    "父系",
    "母系",
    "外祖父",
)

PROFILE_CSV_FIELDS = (
    "horse_no",
    "name",
    "last_race_date",
    "status",
    "profile_last_scraped",
    "出生地",
    "毛色___性別",
    "進口類別",
    "今季獎金",
    "總獎金",
    "冠-亞-季-總出賽次數",
    "練馬師",
    "馬主",
    "最後評分",
    "父系",
    "母系",
    "外祖父",
    "同父系馬",
    "profile_source_url",
    "profile_source_kind",
    "profile_parser_version",
    "profile_checked_at",
    "profile_refresh_status",
    "profile_fields_found",
    "profile_fields_missing",
    "profile_retained_fields",
)


def clean_value(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    text = re.sub(r"\s+", " ", str(value)).strip()
    return "" if text.lower() in {"nan", "none", "null"} else text


def normalize_label(label: object) -> str:
    text = unicodedata.normalize("NFKC", clean_value(label))
    text = re.sub(r"[\s:_./'’*＊()（）]+", "", text)
    return text.lower()


LABEL_ALIASES = {
    "出生地馬齡": "出生地",
    "出生地": "出生地",
    "countryoforiginage": "出生地",
    "毛色性別": "毛色___性別",
    "coloursex": "毛色___性別",
    "進口類別": "進口類別",
    "importtype": "進口類別",
    "今季獎金": "今季獎金",
    "seasonstakes": "今季獎金",
    "總獎金": "總獎金",
    "totalstakes": "總獎金",
    "冠-亞-季-總出賽次數": "冠-亞-季-總出賽次數",
    "冠亞季總出賽次數": "冠-亞-季-總出賽次數",
    "win-2nd-3rd-starts": "冠-亞-季-總出賽次數",
    "練馬師": "練馬師",
    "trainer": "練馬師",
    "馬主": "馬主",
    "owner": "馬主",
    "現時評分": "最後評分",
    "現評": "最後評分",
    "最後評分": "最後評分",
    "currentrating": "最後評分",
    "父系": "父系",
    "sire": "父系",
    "母系": "母系",
    "dam": "母系",
    "外祖父": "外祖父",
    "damsire": "外祖父",
    "同父系馬": "同父系馬",
    "samesire": "同父系馬",
}


def _origin_only(value: str) -> str:
    # Current HKJC label is "出生地 / 馬齡"; the public profile only needs origin.
    return re.split(r"\s*/\s*", value, maxsplit=1)[0].strip()


def canonicalize_pairs(pairs: Iterable[tuple[object, object]]) -> dict[str, str]:
    fields: dict[str, str] = {}
    for raw_label, raw_value in pairs:
        key = LABEL_ALIASES.get(normalize_label(raw_label))
        value = clean_value(raw_value)
        if not key or not value:
            continue
        if key == "出生地":
            value = _origin_only(value)
        fields[key] = value
    return fields


def canonicalize_row(row: Mapping[str, object]) -> dict[str, str]:
    result = {str(key): clean_value(value) for key, value in row.items()}
    aliases = canonicalize_pairs(row.items())
    for key, value in aliases.items():
        if not clean_value(result.get(key)):
            result[key] = value

    # Historical CSVs used dynamic/starred headers. Canonicalize them defensively.
    fallback_aliases = {
        "出生地": ("出生地___馬齡", "出生地 / 馬齡"),
        "今季獎金": ("今季獎金*", "今季獎金＊"),
        "總獎金": ("總獎金*", "總獎金＊"),
        "冠-亞-季-總出賽次數": (
            "冠-亞-季-總出賽次數*",
            "冠-亞-季-總出賽次數＊",
        ),
        "最後評分": ("現時評分",),
    }
    for canonical, candidates in fallback_aliases.items():
        if clean_value(result.get(canonical)):
            continue
        for candidate in candidates:
            value = clean_value(result.get(candidate))
            if value:
                result[canonical] = _origin_only(value) if canonical == "出生地" else value
                break
    public_status = status_from_name(result.get("name"))
    if public_status:
        result["status"] = public_status
    return result


def status_from_name(name: object) -> str | None:
    text = clean_value(name)
    if "已退役" in text:
        return "retired"
    if "已取消登記" in text:
        return "inactive"
    if "已離港" in text:
        return "departed"
    if "已死亡" in text:
        return "deceased"
    return None


class _HorseProfileHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.table_depth = 0
        self.profile_depth: int | None = None
        self.row_stack: list[list[str]] = []
        self.cell_stack: list[list[str]] = []
        self.rows: list[list[str]] = []
        self.title_depth = 0
        self.title_parts: list[str] = []

    @property
    def in_profile(self) -> bool:
        return self.profile_depth is not None and self.table_depth >= self.profile_depth

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = dict(attrs)
        if tag == "table":
            self.table_depth += 1
            classes = (attrs_dict.get("class") or "").split()
            if self.profile_depth is None and "horseProfile" in classes:
                self.profile_depth = self.table_depth
        if not self.in_profile:
            return
        if tag == "tr":
            self.row_stack.append([])
        elif tag in {"td", "th"} and self.row_stack:
            cell: list[str] = []
            self.cell_stack.append(cell)
        classes = (attrs_dict.get("class") or "").split()
        if tag == "span" and "title_text" in classes:
            self.title_depth += 1

    def handle_data(self, data: str) -> None:
        if not self.in_profile:
            return
        if self.cell_stack:
            self.cell_stack[-1].append(data)
        if self.title_depth:
            self.title_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if self.in_profile:
            if tag in {"td", "th"} and self.cell_stack and self.row_stack:
                value = clean_value(" ".join(self.cell_stack.pop()))
                self.row_stack[-1].append(value)
            elif tag == "tr" and self.row_stack:
                row = self.row_stack.pop()
                if row:
                    self.rows.append(row)
            elif tag == "span" and self.title_depth:
                self.title_depth -= 1
        if tag == "table":
            closing_profile = self.profile_depth == self.table_depth
            self.table_depth = max(0, self.table_depth - 1)
            if closing_profile:
                self.profile_depth = None


def parse_profile_html(html: str, horse_no: str) -> dict[str, str]:
    parser = _HorseProfileHTMLParser()
    parser.feed(html)
    pairs = [(row[0], row[2]) for row in parser.rows if len(row) >= 3]
    fields = canonicalize_pairs(pairs)
    name = clean_value(" ".join(parser.title_parts))
    if name:
        fields["name"] = name
        public_status = status_from_name(name)
        if public_status:
            fields["status"] = public_status
    fields["horse_no"] = horse_no
    return fields


def profile_completeness(row: Mapping[str, object]) -> int:
    canonical = canonicalize_row(row)
    return sum(bool(clean_value(canonical.get(key))) for key in PROFILE_COVERAGE_FIELDS)


def merge_profile_rows(
    existing: Mapping[str, object] | None,
    incoming: Mapping[str, object],
) -> dict[str, str]:
    old = canonicalize_row(existing or {})
    new = canonicalize_row(incoming)
    merged = dict(old)

    for key, value in new.items():
        if clean_value(value):
            merged[key] = clean_value(value)

    retained = [
        key
        for key in CANONICAL_PROFILE_FIELDS
        if clean_value(old.get(key)) and not clean_value(new.get(key))
    ]
    incoming_found = [
        key for key in PROFILE_COVERAGE_FIELDS if clean_value(new.get(key))
    ]
    incoming_missing = [
        key for key in PROFILE_COVERAGE_FIELDS if not clean_value(new.get(key))
    ]
    old_score = profile_completeness(old)
    new_score = profile_completeness(new)

    if retained and old_score > new_score:
        merged["profile_refresh_status"] = "partial_merged"
        # Keep the older truthful data cutoff when values had to be retained.
        if clean_value(old.get("profile_last_scraped")):
            merged["profile_last_scraped"] = clean_value(old["profile_last_scraped"])
    else:
        merged["profile_refresh_status"] = "complete" if not incoming_missing else "partial"

    merged["profile_fields_found"] = "|".join(incoming_found)
    merged["profile_fields_missing"] = "|".join(incoming_missing)
    merged["profile_retained_fields"] = "|".join(retained)
    return merged