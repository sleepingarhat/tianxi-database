# Data Integrity Audit · 2026-07-30

**Overall:** 🟡 `warn`  ·  critical gaps: **0**  ·  warn gaps: 6

**Recommendation:** `monitor_no_block`

## Per-category

| Category | Severity | Expected | Present | Missing | Stale | Notes |
|---|---|---|---|---|---|---|
| race_artefacts | 🟢 ok | 715 | 715 | 0 | 0 |  |
| fixtures_cache | 🟢 ok | 1 | 238 | 0 | 0 | total cached race days: 238 |
| horse_profiles | 🟢 ok | 1272 | 1272 | 0 | 0 | total profiles in DB: 6063 |
| horse_form_records | 🟢 ok | 1272 | 1272 | 0 | 0 | total form_records files: 6063 |
| jockey_profiles | 🟢 ok | 34 | 34 | 0 | 0 | total jockey profiles: 64 |
| jockey_records | 🟡 warn | 64 | 59 | 5 | 0 | 5 jockey profiles have no records file |
| trainer_profiles | 🟢 ok | 34 | 34 | 0 | 0 | total trainer profiles: 67 |
| trainer_records | 🟢 ok | 67 | 67 | 0 | 0 |  |
| trial_results | 🟢 ok | 1 | 1 | 0 | 0 | trial rows: 7071 |
| entries_upcoming | 🟡 warn | 1 | 0 | 1 | 0 | 1 upcoming race days lack entries file |
