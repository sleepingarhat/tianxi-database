"""
Trackwork (晨操紀錄) parser — STUB.

Will be filled when Pool B parity-testing begins. Phase 0 / P0 scope is
trainer fix + entries + race_day. See HANDOVER.md §B-extra-2 for rate limits.

Schema reference (TBD, matches Replit horses/trackwork/trackwork_XXX.csv).
"""
from __future__ import annotations

from typing import Any

TRACKWORK_COLS: list[str] = [
    "horse_no", "date", "racecourse", "track", "session_type", "distance_m",
    "time", "jockey", "gear", "notes",
]


def parse_trackwork(html: str, horse_no: str) -> list[dict[str, Any]]:
    """TODO: implement after P0 ships. Returns empty list for now."""
    return []
