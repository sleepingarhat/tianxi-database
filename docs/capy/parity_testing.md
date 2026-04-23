# Capy ↔ Replit Parity Testing

This document defines how the Capy scraper output (`scrapers_v2/`) is verified
byte-for-byte against Replit's existing pipeline (`RacingData_Scraper.py`).

## Why byte-parity?

The downstream ETL (ELO model v11, Pool B enrichment, production dashboards)
has been tuned against Replit's exact CSV byte layout — column order, BOM,
line endings, numeric formatting, Chinese punctuation, empty-cell semantics.
If we drift, downstream silently mis-aggregates.

## Goals

1. **Column schema match** — same `fieldnames`, same order, no extras.
2. **Row-set match** — same set of `(pk)` tuples per file. Order may differ
   if both CSVs are sorted identically; otherwise compare as sets.
3. **Cell-value match** — for each shared row, each cell is byte-equal after
   trivial whitespace collapse.

## Scope

| File family                       | Source              | Parity target                      |
|-----------------------------------|---------------------|------------------------------------|
| `data/YYYY/results_*.csv`         | LocalResults.aspx   | Replit 25 cols, exact              |
| `data/YYYY/sectional_times_*.csv` | LocalResults.aspx   | Replit 25 cols, exact              |
| `data/YYYY/commentary_*.csv`      | LocalResults.aspx   | Replit 9 cols, exact               |
| `data/YYYY/dividends_*.csv`       | LocalResults.aspx   | Replit 6 cols, exact               |
| `data/YYYY/video_links_*.csv`     | LocalResults.aspx   | Replit 6 cols, exact               |
| `entries/entries_YYYY-MM-DD.txt`  | RaceCard.aspx       | Replit txt (deduped brand codes)   |
| `horses/profiles/*.csv`           | Horse.aspx          | Replit 16 cols                     |
| `horses/form_records/form_*.csv`  | Horse.aspx          | Replit 21 cols                     |
| `trainers/trainer_profiles.csv`   | TrainerProfile.aspx | Capy: 14 cols (Replit had 2 bugged — fix supersedes parity) |
| `trainers/records/*.csv`          | TrainerPastRec.aspx | Capy-new (no Replit equivalent)    |
| `entries/races/*_r*.csv`          | RaceCard.aspx       | Capy-new                           |

## Harness: `tests/parity/`

```
tests/parity/
├── __init__.py
├── conftest.py                 # fixtures: load_replit(), load_capy()
├── test_results_parity.py      # data/YYYY/results_*.csv
├── test_sectional_parity.py
├── test_commentary_parity.py
├── test_dividends_parity.py
├── test_videos_parity.py
├── test_entries_txt_parity.py
├── test_horse_profile_parity.py
├── test_horse_form_parity.py
└── golden/                      # frozen Replit outputs for regression
    ├── 2026-04-19_ST/           # a fixed Sunday meeting
    └── horse_form_K056_v1.csv
```

## Comparison rules

### Hash mode (strict)
```python
import hashlib
def sha256_of(path): return hashlib.sha256(path.read_bytes()).hexdigest()
assert sha256_of(capy_csv) == sha256_of(replit_csv)
```
Used for: files we expect to produce verbatim (entries .txt).

### Normalized mode (lenient)
```python
import pandas as pd
df_r = pd.read_csv(replit_csv, encoding="utf-8-sig", dtype=str).fillna("")
df_c = pd.read_csv(capy_csv,  encoding="utf-8-sig", dtype=str).fillna("")
# sort both by primary key, reset index
df_r = df_r.sort_values(PK).reset_index(drop=True)
df_c = df_c.sort_values(PK).reset_index(drop=True)
pd.testing.assert_frame_equal(df_r, df_c, check_dtype=False)
```
Used for: all multi-row CSVs where row order may legitimately differ.

### Tolerant mode (numeric wiggle)
For cells flagged `{win_odds, time_sec, sectional_time_*}` — allow ±0.01
absolute difference because HKJC sometimes serves slightly rounded values
between HTML fetches.

## Primary keys (PK)

| File            | PK                                           |
|-----------------|----------------------------------------------|
| results         | `(race_date, venue, race_no, horse_no)`      |
| sectional_times | `(race_date, venue, race_no, horse_no)`      |
| commentary      | `(race_date, venue, race_no, horse_no)`      |
| dividends       | `(race_date, venue, race_no, pool, combo)`   |
| video_links     | `(race_date, venue, race_no, video_type)`    |
| horse_profile   | `horse_no`                                   |
| horse_form      | `(horse_no, race_index)`                     |

## CI integration

`.github/workflows/capy_parity.yml` (future):
1. Checkout Replit latest main (read-only pull).
2. Checkout capy/scraper-v2.
3. Run `pytest tests/parity/ -v` comparing same race-day snapshot.
4. Fail the check on any frame-equality violation.

Until the feature branch lands on main, parity tests are run locally with:
```bash
cd hkjc-data
pytest tests/parity/ -v --replit-root=../replit-mirror --capy-root=.
```

## Known deliberate divergences

These are NOT bugs — they are intentional fixes. Parity tests whitelist them.

| File                          | Divergence                                     | Reason                  |
|-------------------------------|------------------------------------------------|-------------------------|
| trainers/trainer_profiles.csv | 14 cols vs Replit 2 cols                       | Replit D1 silent-fail   |
| trainers/trainer_profiles.csv | Deduped by trainer_id                          | Replit had 1431 dupes   |
| trainers/records/             | New directory                                  | Replit never produced   |
| entries/races/*.csv           | New per-race CSVs                              | Replit only kept .txt   |

## Baseline tag

Replit will set `capy-handover-baseline-v1` on their repo at **2026-04-26 12:00 UTC**.
That commit is the frozen reference — all Capy parity tests run against CSVs
at that SHA. Subsequent Replit commits after baseline are ignored until the
next baseline-vN tag.
