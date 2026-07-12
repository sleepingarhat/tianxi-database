# Data Integrity Audit · 2026-07-12

**Overall:** 🟡 `warn`  ·  critical gaps: **0**  ·  warn gaps: 18

**Recommendation:** `monitor_no_block`

## Per-category

| Category | Severity | Expected | Present | Missing | Stale | Notes |
|---|---|---|---|---|---|---|
| race_artefacts | 🟢 ok | 710 | 710 | 0 | 0 |  |
| fixtures_cache | 🟢 ok | 1 | 143 | 0 | 0 | total cached race days: 143 |
| horse_profiles | 🟡 warn | 1293 | 1293 | 0 | 12 | 12 profiles are stale (profile_last_scraped < last_race_date); total profiles in DB: 6057 |
| horse_form_records | 🟢 ok | 1293 | 1293 | 0 | 0 | total form_records files: 6057 |
| jockey_profiles | 🟢 ok | 34 | 34 | 0 | 0 | total jockey profiles: 64 |
| jockey_records | 🟡 warn | 64 | 59 | 5 | 0 | 5 jockey profiles have no records file |
| trainer_profiles | 🟢 ok | 34 | 34 | 0 | 0 | total trainer profiles: 67 |
| trainer_records | 🟢 ok | 67 | 67 | 0 | 0 |  |
| trial_results | 🟢 ok | 1 | 1 | 0 | 0 | trial rows: 7071 |
| entries_upcoming | 🟡 warn | 2 | 1 | 1 | 0 | 1 upcoming race days lack entries file |
