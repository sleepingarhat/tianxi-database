# Data Integrity Audit · 2026-07-02

**Overall:** 🔴 `critical`  ·  critical gaps: **1**  ·  warn gaps: 7

**Recommendation:** `gha_next_delta_will_fix`

## Per-category

| Category | Severity | Expected | Present | Missing | Stale | Notes |
|---|---|---|---|---|---|---|
| race_artefacts | 🟢 ok | 695 | 695 | 0 | 0 |  |
| fixtures_cache | 🟢 ok | 1 | 143 | 0 | 0 | total cached race days: 143 |
| horse_profiles | 🟢 ok | 1290 | 1290 | 0 | 0 | total profiles in DB: 6046 |
| horse_form_records | 🔴 critical | 1290 | 1289 | 1 | 0 | 1 recent-cohort horses have NO form_records file; total form_records files: 6045 |
| jockey_profiles | 🟢 ok | 34 | 34 | 0 | 0 | total jockey profiles: 64 |
| jockey_records | 🟡 warn | 64 | 59 | 5 | 0 | 5 jockey profiles have no records file |
| trainer_profiles | 🟢 ok | 34 | 34 | 0 | 0 | total trainer profiles: 67 |
| trainer_records | 🟢 ok | 67 | 67 | 0 | 0 |  |
| trial_results | 🟢 ok | 1 | 1 | 0 | 0 | trial rows: 7011 |
| entries_upcoming | 🟡 warn | 2 | 0 | 2 | 0 | 2 upcoming race days lack entries file |

### 🔴 horse_form_records — sample missing (first 20)

```
L346
```
