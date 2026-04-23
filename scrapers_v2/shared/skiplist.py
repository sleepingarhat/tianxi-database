"""
Phantom horse skiplist — known-bad horse_no values where HKJC Horse.aspx
returns no tables (horse appeared in historical race results but profile
was later archived/deleted by HKJC).

Source: Replit prod ephemeral failed_horses.log (~30 entries, 2026-04-22).
Caveat: Replit's failed_horses.log is .gitignore'd, so this list is a
one-time snapshot bootstrap. Orchestrator extends it at runtime.

Field identity reminder (per Replit handover):
- `horse_no`  = brand code e.g. "A111", "C408"  (Horse.aspx?HorseNo=...)
- `horse_id`  = "HK_YYYY_BRAND"                  (ovehorse / injury URL)
Skip logic must use horse_no, not horse_id.
"""

from __future__ import annotations

# Phantom horses — skip BEFORE profile fetch to save HTTP budget.
# Behavior: all return 200 OK but the page body contains no horse data tables,
# so Horse.aspx parser would emit no rows anyway. Retrying is pointless.
PHANTOM_HORSE_NOS: frozenset[str] = frozenset({
    "A111", "A112", "A113", "A117", "A118",
    "A120", "A121", "A123", "A124", "A125",
    "A127", "A128", "A129",
    "A133", "A135", "A136", "A137", "A138", "A139",
    "A141", "A144", "A145", "A146", "A148", "A149",
    "A150", "A152", "A156",
    "C408",
})


def is_phantom(horse_no: str) -> bool:
    """True if horse_no is known-archived / empty profile."""
    return (horse_no or "").strip().upper() in PHANTOM_HORSE_NOS
