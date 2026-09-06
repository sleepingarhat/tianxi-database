# Data Integrity Audit · 2026-09-06

**Overall:** 🟡 `warn`  ·  critical gaps: **0**  ·  warn gaps: 19

**Recommendation:** `monitor_no_block`

## Per-category

| Category | Severity | Expected | Present | Missing | Stale | Notes |
|---|---|---|---|---|---|---|
| race_artefacts | 🟢 ok | 720 | 720 | 0 | 0 |  |
| fixtures_cache | 🟢 ok | 1 | 231 | 0 | 0 | total cached race days: 231 |
| horse_profiles | 🟡 warn | 1209 | 1209 | 0 | 12 | 12 profiles are stale (profile_last_scraped < last_race_date); total profiles in DB: 6065 |
| horse_form_records | 🟢 ok | 1209 | 1209 | 0 | 0 | total form_records files: 6065 |
| jockey_profiles | 🟢 ok | 33 | 33 | 0 | 0 | total jockey profiles: 64 |
| jockey_records | 🟡 warn | 64 | 59 | 5 | 0 | 5 jockey profiles have no records file |
| trainer_profiles | 🟢 ok | 34 | 34 | 0 | 0 | total trainer profiles: 67 |
| trainer_records | 🟢 ok | 67 | 67 | 0 | 0 |  |
| trial_results | 🟢 ok | 1 | 1 | 0 | 0 | trial rows: 8259 |
| entries_upcoming | 🟡 warn | 3 | 1 | 2 | 0 | 2 upcoming race days lack entries file |
