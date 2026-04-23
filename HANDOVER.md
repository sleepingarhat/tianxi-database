# HKJC Scraper — Handover Document (Replit → GitHub Actions)

**Cut-off date:** 2026-04-22 21:00 UTC
**Last commit at write time:** `5dc4752bab17` (2026-04-22T20:42Z)
**Final baseline tag (planned):** `capy-handover-baseline-v1` at 4/26 12:00 UTC after Full dataset complete
**Repo:** `sleepingarhat/hkjc-horse-racing-results` · branch `main`
**Receiving party:** Capy / GitHub Actions runner

---

## A · Operational State

### A1 · Current commit cadence
- 30-minute periodic backups via `git_sync_periodic.py` (Replit Reserved VM)
- Commit author: `天喜 Bot <bot@tianxi.ai>`
- Subject prefix: `[data][skip ci] periodic backup ...`
- Pull latest before handover: always re-query `GET /repos/.../commits?per_page=1`

### A2 · GH_TOKEN (Replit Secrets)
- **Owner:** `sleepingarhat` (Personal account)
- **Type:** Classic PAT
- **Scopes (overly broad):** `repo, workflow, admin:org, admin:enterprise, admin:gpg_key, admin:repo_hook, admin:org_hook, admin:public_key, admin:ssh_signing_key, audit_log, codespace, copilot, delete:packages, delete_repo, gist, notifications, project, user, write:discussion, write:network_configurations, write:packages`
- **Rate limit:** 5000 req/hr
- **Expiry:** Not exposed via API — check at github.com/settings/tokens
- **Recommendation for Capy:** Issue a NEW fine-grained PAT scoped to this single repo with only `Contents: R/W` + `Actions: R/W`. Replit-side token to be revoked at Phase 2 cutover.

### A3 · Schedulers — there is NO system cron in Replit
Production runs as an always-on Reserved VM via `run_all_scrapers.sh`:
```
run_all_scrapers.sh
├─ inventory_server.py            (HTTP :5000, /inventory /diag /head/<path>)
├─ git_sync_periodic.py           (10min warm-up → 30min push loop, --no-push for pools)
├─ Pool A (forever loop):  HorseData → HorseTrackwork → HorseInjury    (~25h/cycle)
└─ Pool B (forever loop):  Trial → Entry → Jockey → Trainer            (~5min/cycle)
```
The only cron is the GitHub Actions stale workflow — see C1.

### A4 · Trainer scraper status (D1 issue)
- `trainers/trainer_profiles.csv` — 67 unique trainers, but historically 1431 rows due to dedup bug
- **Hotfix applied 2026-04-22:** `TrainerData_Scraper.py` now uses `keep="last"` and runs a startup cleanup (one-time pass strips dupes when scraper next runs after 4/26 republish)
- `trainers/records/` — does NOT exist on GitHub. Trainer past-records have NEVER been successfully scraped (HKJC trainer-ranking SPA breakage). Capy's Phase 0 should rebuild this from scratch.
- `trainer_profiles.csv` columns: only `trainer_code, trainer_name` (stats parsing silently fails on SPA)

---

## B · Edge Cases

### B1 · HKJC IP ban / 429 / Cloudflare
- **No evidence of any IP ban** in deployment history.
- `failed_dates.log` only contains 2 entries from 2016-01-02/03 (no races those days).
- `failed_horses.log` ~30 entries, all reason: `no tables found` (first-race horses with empty profiles).
- Deployment log scan for `429|blocked|forbidden|cloudflare|captcha|rate.?limit` → zero matches.
- Only error pattern: occasional `socket timeout` (already retried 3× by `scraper_utils.load_page`).
- **Recommendation for Capy:** Throttle to ≥0.5 req/s per scraper; current prod runs ~3000 req/hr safely.

### B2 · Horse queue — ACTUAL count = 5,827 (NOT 3000)
- Source: regex `r"\(([A-Z]\d+)\)"` over `data/YEAR/results_*.csv` `horse_name` field
- **No sharding** — single-process A→Z sequential loop
- **No dead-ID list** maintained — failures append to `failed_horses.log`, no auto-retry
- Idempotency: `form_XXXX.csv` exists → skip (so Capy's GHA can resume safely)

### B3 · Trial scraper — retired horse handling
- **No `is_retired` filter** in `TrialResults_Scraper.py`. All horses appearing on `btresult` are recorded raw.
- Tianxi side must JOIN `horses/profiles/horse_profiles.csv → status` to filter retired.
- HKJC `btresult` enforces a 176-day sliding window on the date dropdown (server-side).

### B4 · HTML format variants (known)
| Page | Variant | Scraper handling |
|---|---|---|
| `Horse.aspx` | First-race horse, no form table | `if not form_table: continue` |
| `Horse.aspx` | Retired horse name has `(已退役)` suffix | NOT stripped — Tianxi must handle |
| `trackworkresult` | No URL/data for new horses | Empty CSV placeholder written |
| `trainer-ranking` | SPA → stats/records detection breaks | Silent fail (D1 bug) |
| `racecard` | "沒有相關資料" sentinel vs render timeout | Distinguished, fail-closed |
| `ovehorse` | `horseid` re-registered (`HK_2023_X` → `HK_2024_X`) | Cache invalidate + 1 retry |

### B5 · Encoding & misc
- All CSV writes use **`utf-8-sig`** (UTF-8 BOM) for Excel-friendly Chinese.
- HKJC SPA pages (`/local/info/...`) **require Selenium**. Old `.aspx` URLs are server-rendered (`requests` works for `HorseInjury_Scraper.py` only).

---

## C · Handover Logistics

### C1 · Existing GitHub Actions workflow — `update-hkjc-scraper.yml`
- **Status: STALE, runs daily at UTC 03:30 (HKT 11:30) but silently no-ops** because `RacingData_Scraper.py` uses hardcoded date ranges that are already fully scraped.
- Capy's plan: keep this enabled until new `capy_race_daily.yml` ships, then disable in same PR (`on: {}` or `git rm`).

### C2 · Repo files — Capy `.gitignore` candidates
These mutable files cause merge conflicts; recommend Capy `.gitignore` them in feature branches:
- `last_sync.json` (rewritten every 30min)
- `failed_*.log` (append-only)
- `horses/injury/_horseid_map.json` (cache)

### C3 · Phase 1 stop procedure (Replit side)
1. Wait for Capy's parity test pass signal
2. Run final `python git_sync.py --message "final sync before handover SHA=XXX"`
3. Tag at 4/26 12:00 UTC: `git tag capy-handover-baseline-v1 <sha> && git push origin --tags`
4. Stop Reserved VM (Replit Settings → Stop Deployment)
5. Keep `GH_TOKEN` and repo intact during 1–2 week parity window

### C4 · Phase 2 final cutover (1–2 weeks after Phase 1)
1. Capy confirms 4 parity criteria all pass (see below)
2. Revoke Replit-side `GH_TOKEN`
3. Archive Replit project (do NOT delete for ≥1 month)

---

## D · Per-scraper request rate (for Capy GHA alignment)

Approximate steady-state rates (selenium overhead included):

| Scraper | Sleep config | Effective rate |
|---|---|---|
| `HorseData_Scraper.py` | `sleep(1)` per horse | ~0.5–1 req/s |
| `HorseTrackwork_Scraper.py` | `sleep(1)` × 2 navigations | ~0.5 req/s |
| `HorseInjury_Scraper.py` | `SLEEP_BETWEEN = 0.4` (pure requests) | ~2.5 req/s |
| `TrialResults_Scraper.py` | `sleep(2)` per date page + `sleep(1.5)` | ~0.4 req/s |
| `EntryList_Scraper.py` | `sleep(0.6)` polling + `sleep(2)` per race | ~1.0–1.5 req/s |
| `JockeyData_Scraper.py` | `sleep(1–2)` per jockey/season | ~0.5 req/s |
| `TrainerData_Scraper.py` | `sleep(1–2)` per trainer/season | ~0.25 req/s |

All `load_page` calls retry up to 3× with built-in 30s timeout (`scraper_utils.py`).

---

## E · CSV Schema (pinned column counts)

| File | Columns | Stable? |
|---|---|---|
| `horses/form_records/form_XXXX.csv` | 21 hardcoded | ✅ |
| `data/YYYY/results_*.csv` | 25 hardcoded | ✅ |
| `trials/trial_results.csv` | 18 hardcoded | ✅ |
| `jockeys/records/jockey_*.csv` | 19 hardcoded + extras | ✅ |
| `horses/trackwork/trackwork_*.csv` | 7 hardcoded | ✅ |
| `horses/injury/injury_*.csv` | 4 hardcoded (horse_no, date, detail, cleared_date) | ✅ |
| `horses/profiles/horse_profiles.csv` | DYNAMIC (Chinese label keys) | ⚠️ Use column NAME match |
| `trainers/trainer_profiles.csv` | DYNAMIC (currently 2 cols only due to D1) | ⚠️ |
| `trainers/records/trainer_*.csv` | 21 (RECORD_COLS) — but file currently absent | n/a |

---

## F · Known issues handed over to Capy

1. **Trainer SPA stats parsing** — `TrainerData_Scraper.py` line 110–119 uses `row.text.split("  ")` (2 spaces) which doesn't match new SPA HTML. Stats columns silently lost. Capy may re-implement from scratch.
2. **Trainer past-records absent** — `trainers/records/` dir never populated. Capy Phase 0 to rebuild.
3. **Horse name `(已退役)` suffix** — not stripped at scraper level; Tianxi/Capy parser must handle.
4. **Dynamic `horse_profiles.csv` columns** — use column name match, NOT positional index.
5. **No retry mechanism for `failed_*.log`** — Capy GHA should periodically re-attempt.

---

## G · Parity exit criteria (Capy-defined, agreed)

All four MUST pass for Phase 2 cutover:
1. ✅ Trainer fix: Capy GHA produces all 67 trainers with full `records/` dir + complete stats.
2. ✅ Entries: Capy daily `racecard` CSV row-by-row matches Replit `EntryList/*.csv`.
3. ✅ Race day: 4/22, 4/26, 4/29 race results — Capy independent scrape produces cell-level diff = 0 vs Replit.
4. ✅ Horse form: 10 sample horses' `form_XXXX.csv` 21 cols 100% identical.

---

*Maintained by Replit-side until Phase 2 cutover. After cutover this file is read-only historical reference.*
