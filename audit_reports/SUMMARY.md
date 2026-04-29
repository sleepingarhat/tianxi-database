# Data Integrity Audit · 2026-04-29

**Overall:** 🔴 `critical`  ·  critical gaps: **11**  ·  warn gaps: 75

**Recommendation:** `gha_next_delta_will_fix`

## Per-category

| Category | Severity | Expected | Present | Missing | Stale | Notes |
|---|---|---|---|---|---|---|
| race_artefacts | 🔴 critical | 610 | 600 | 10 | 0 | days with any missing artefact: 2 |
| fixtures_cache | 🟢 ok | 1 | 143 | 0 | 0 | total cached race days: 143 |
| horse_profiles | 🟢 ok | 1275 | 1275 | 0 | 0 | total profiles in DB: 5933 |
| horse_form_records | 🟢 ok | 1275 | 1275 | 0 | 0 | total form_records files: 5933 |
| jockey_profiles | 🔴 critical | 45 | 44 | 1 | 0 | 1 jockeys raced recently but NO profile; total jockey profiles: 64 |
| jockey_records | 🟡 warn | 64 | 59 | 5 | 0 | 5 jockey profiles have no records file |
| trainer_profiles | 🟢 ok | 38 | 38 | 0 | 0 | total trainer profiles: 67 |
| trainer_records | 🟡 warn | 67 | 0 | 67 | 0 | 67 trainer profiles have no records file |
| trial_results | 🟢 ok | 1 | 1 | 0 | 0 | trial rows: 5733 |
| entries_upcoming | 🟡 warn | 3 | 0 | 3 | 0 | 3 upcoming race days lack entries file |

### 🔴 race_artefacts — sample missing (first 20)

```
results_2026-04-26
commentary_2026-04-26
dividends_2026-04-26
sectional_times_2026-04-26
video_links_2026-04-26
results_2026-04-29
commentary_2026-04-29
dividends_2026-04-29
sectional_times_2026-04-29
video_links_2026-04-29
```

### 🔴 jockey_profiles — sample missing (first 20)

```
---
```
