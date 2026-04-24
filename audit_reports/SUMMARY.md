# Data Integrity Audit · 2026-04-24

**Overall:** 🔴 `critical`  ·  critical gaps: **2587**  ·  warn gaps: 73

**Recommendation:** `replit_fallback_required`

## Per-category

| Category | Severity | Expected | Present | Missing | Stale | Notes |
|---|---|---|---|---|---|---|
| race_artefacts | 🔴 critical | 640 | 590 | 50 | 0 | days with any missing artefact: 10 |
| fixtures_cache | 🟢 ok | 1 | 151 | 0 | 0 | total cached race days: 151 |
| horse_profiles | 🔴 critical | 1272 | 4 | 1268 | 0 | 1268 horses raced in last 180d have NO profile; total profiles in DB: 1886 |
| horse_form_records | 🔴 critical | 1272 | 4 | 1268 | 0 | 1268 recent-cohort horses have NO form_records file; total form_records files: 1899 |
| jockey_profiles | 🔴 critical | 44 | 43 | 1 | 0 | 1 jockeys raced recently but NO profile; total jockey profiles: 64 |
| jockey_records | 🟡 warn | 64 | 59 | 5 | 0 | 5 jockey profiles have no records file |
| trainer_profiles | 🟢 ok | 38 | 38 | 0 | 0 | total trainer profiles: 67 |
| trainer_records | 🟡 warn | 67 | 0 | 67 | 0 | 67 trainer profiles have no records file |
| trial_results | 🟢 ok | 1 | 1 | 0 | 0 | trial rows: 5579 |
| entries_upcoming | 🟡 warn | 2 | 1 | 1 | 0 | 1 upcoming race days lack entries file |

### 🔴 race_artefacts — sample missing (first 20)

```
results_2025-08-07
commentary_2025-08-07
dividends_2025-08-07
sectional_times_2025-08-07
video_links_2025-08-07
results_2025-08-10
commentary_2025-08-10
dividends_2025-08-10
sectional_times_2025-08-10
video_links_2025-08-10
results_2025-08-14
commentary_2025-08-14
dividends_2025-08-14
sectional_times_2025-08-14
video_links_2025-08-14
results_2025-08-17
commentary_2025-08-17
dividends_2025-08-17
sectional_times_2025-08-17
video_links_2025-08-17
```

### 🔴 horse_profiles — sample missing (first 20)

```
D075
E058
E061
E175
E184
E301
E321
E356
E392
E403
E413
E430
E432
E434
E435
E436
E448
E459
E471
E472
```

### 🔴 horse_form_records — sample missing (first 20)

```
D075
E058
E061
E175
E184
E301
E321
E356
E392
E403
E413
E430
E432
E434
E435
E436
E448
E459
E471
E472
```

### 🔴 jockey_profiles — sample missing (first 20)

```
---
```
