# Data Integrity Audit · 2026-09-05

**Overall:** 🔴 `critical`  ·  critical gaps: **35**  ·  warn gaps: 6

**Recommendation:** `gha_next_delta_will_fix`

## Per-category

| Category | Severity | Expected | Present | Missing | Stale | Notes |
|---|---|---|---|---|---|---|
| race_artefacts | 🔴 critical | 750 | 715 | 35 | 0 | days with any missing artefact: 7 |
| fixtures_cache | 🟢 ok | 1 | 238 | 0 | 0 | total cached race days: 238 |
| horse_profiles | 🟢 ok | 1209 | 1209 | 0 | 0 | total profiles in DB: 6063 |
| horse_form_records | 🟢 ok | 1209 | 1209 | 0 | 0 | total form_records files: 6063 |
| jockey_profiles | 🟢 ok | 33 | 33 | 0 | 0 | total jockey profiles: 64 |
| jockey_records | 🟡 warn | 64 | 59 | 5 | 0 | 5 jockey profiles have no records file |
| trainer_profiles | 🟢 ok | 34 | 34 | 0 | 0 | total trainer profiles: 67 |
| trainer_records | 🟢 ok | 67 | 67 | 0 | 0 |  |
| trial_results | 🟢 ok | 1 | 1 | 0 | 0 | trial rows: 7071 |
| entries_upcoming | 🟡 warn | 2 | 1 | 1 | 0 | 1 upcoming race days lack entries file |

### 🔴 race_artefacts — sample missing (first 20)

```
results_2026-08-06
commentary_2026-08-06
dividends_2026-08-06
sectional_times_2026-08-06
video_links_2026-08-06
results_2026-08-09
commentary_2026-08-09
dividends_2026-08-09
sectional_times_2026-08-09
video_links_2026-08-09
results_2026-08-13
commentary_2026-08-13
dividends_2026-08-13
sectional_times_2026-08-13
video_links_2026-08-13
results_2026-08-16
commentary_2026-08-16
dividends_2026-08-16
sectional_times_2026-08-16
video_links_2026-08-16
```
