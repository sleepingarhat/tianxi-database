"""HKJC parsers — one module per endpoint family. Column schemas are pinned
inside each parser to prevent silent drift when HKJC changes HTML layout.
"""
from . import (  # noqa: F401
    entries,
    horse_form,
    horse_profile,
    injury,
    race_results,
    trackwork,
    trainer,
)

__all__ = [
    "entries",
    "horse_form",
    "horse_profile",
    "injury",
    "race_results",
    "trackwork",
    "trainer",
]
