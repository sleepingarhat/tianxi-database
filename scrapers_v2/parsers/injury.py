"""
Injury (傷患紀錄) parser — STUB.

Replit note: pure-requests endpoint (no Selenium), rate 2.5 req/s safe.
Schema TBD. Fill during Pool B parity-testing phase.

Replit source URL pattern (approx; confirm via HANDOVER.md):
    https://racing.hkjc.com/racing/information/chinese/Horse/OveHorse.aspx
      ?HorseId=HK_YYYY_XXX
"""
from __future__ import annotations

from typing import Any

INJURY_COLS: list[str] = [
    "horse_id", "horse_no", "date_from", "date_to", "injury_type", "notes",
]


def parse_injury(html: str, horse_id: str) -> list[dict[str, Any]]:
    """TODO: implement after P0 ships. Returns empty list for now."""
    return []
