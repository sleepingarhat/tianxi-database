"""Canonical output paths — must match Replit layout for CSV parity."""
from __future__ import annotations

from pathlib import Path

# Root of hkjc-data repo (auto-detect via walking up from this file)
REPO_ROOT = Path(__file__).resolve().parents[2]

# Primary output dirs (must match Replit)
DATA_DIR = REPO_ROOT / "data"
HORSES_DIR = REPO_ROOT / "horses"
JOCKEYS_DIR = REPO_ROOT / "jockeys"
TRAINERS_DIR = REPO_ROOT / "trainers"
TRIALS_DIR = REPO_ROOT / "trials"
ENTRIES_DIR = REPO_ROOT / "entries"

# Sub-dirs
HORSE_PROFILES_DIR = HORSES_DIR / "profiles"
HORSE_FORM_DIR = HORSES_DIR / "form_records"
HORSE_TRACKWORK_DIR = HORSES_DIR / "trackwork"
HORSE_INJURY_DIR = HORSES_DIR / "injury"
JOCKEY_RECORDS_DIR = JOCKEYS_DIR / "records"
TRAINER_RECORDS_DIR = TRAINERS_DIR / "records"

# Staging dir (for parity testing)
STAGING_DIR = REPO_ROOT / "staging_v2"

# Sync metadata
LAST_SYNC_JSON = REPO_ROOT / "last_sync.json"

# Capy-specific state
CAPY_STATE_DIR = REPO_ROOT / ".capy"


def ensure_dirs() -> None:
    """Create all output dirs if they don't exist."""
    for d in [
        DATA_DIR,
        HORSE_PROFILES_DIR,
        HORSE_FORM_DIR,
        HORSE_TRACKWORK_DIR,
        HORSE_INJURY_DIR,
        JOCKEY_RECORDS_DIR,
        TRAINER_RECORDS_DIR,
        TRIALS_DIR,
        ENTRIES_DIR,
        CAPY_STATE_DIR,
    ]:
        d.mkdir(parents=True, exist_ok=True)


def data_year_dir(year: int) -> Path:
    d = DATA_DIR / str(year)
    d.mkdir(parents=True, exist_ok=True)
    return d
