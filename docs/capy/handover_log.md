# Capy ↔ Replit Handover Log

Chronological journal of the handover from Replit's Selenium scraper to Capy's
httpx async pipeline. Each entry is dated and attributed.

## 2026-04-22 — Session 2.9 (Capy)

**Built by Capy on `capy/scraper-v2` feature branch.**

Parsers (7 total):
- `scrapers_v2/parsers/entries.py` — RaceCard.aspx (32 + 14 cols)
- `scrapers_v2/parsers/race_results.py` — LocalResults.aspx (5 tables: 25/25/9/6/6)
- `scrapers_v2/parsers/horse_profile.py` — Horse.aspx profile block (16 cols)
- `scrapers_v2/parsers/horse_form.py` — Horse.aspx form records (21 cols)
- `scrapers_v2/parsers/trainer.py` — TrainerProfile + TrainerPastRec (14 + 18 cols)
- `scrapers_v2/parsers/trackwork.py` — Pool B stub
- `scrapers_v2/parsers/injury.py` — Pool B stub

Orchestrators (4 total):
- `scrapers_v2/orchestrator/daily/scrape_entries.py` — 0.8 req/s
- `scrapers_v2/orchestrator/daily/scrape_race_day.py` — 0.5 req/s, 5 CSV writes
- `scrapers_v2/orchestrator/daily/scrape_trainers.py` — 0.25 req/s, D1 fix
- `scrapers_v2/orchestrator/pool_a/scrape_horses.py` — 0.5 req/s, chunked 50

GitHub Actions workflows (4 `capy_*.yml`):
- `capy_race_daily.yml` — UTC 15:30 daily (HK 23:30)
- `capy_entries.yml` — UTC 12:00 Mon/Tue/Sat (HK 20:00)
- `capy_trainer_fix.yml` — UTC 17:00 daily (HK 01:00)
- `capy_pool_a.yml` — UTC 20:00 Saturday (HK 04:00 Sun), weekly

Phantom skiplist: `scrapers_v2/shared/skiplist.py` — 29 brand codes (A111–A156, C408).

Key corrections this session:
- Horse universe size: 3,000 → **5,827** (derived from results CSV history).
- Phantom horse key: `horse_id` → **`horse_no`** (Horse.aspx uses raw brand code).
- Trainer records parser rewritten: original version assumed flat table, real
  HKJC uses date-section-header row pattern (single-cell `22/04/2026 跑馬地`
  rows alternating with 16-cell data rows).
- `race_class` regex fixed: `(第.+?班|國際.+?級|.*?賽事)` → non-pipe-crossing
  `(第[一二三四五六七八九十]+班|國際[一二三四五]+級|[^|]*?賽事)`.

Open items pending Replit action:
- HANDOVER.md push to main (awaiting user 推咗 signal).
- Baseline tag `capy-handover-baseline-v1` at 2026-04-26 12:00 UTC.

## 2026-04-20 — Session 2.8 (Capy)

**Groundwork by Capy.**

- `scrapers_v2/http_client/base.py` — `AsyncHKJCClient` with rate-limit & retry.
- `scrapers_v2/shared/paths.py` — centralized dir constants (DATA_DIR, HORSE_*_DIR, etc.).
- `scrapers_v2/shared/utils.py` — `clean_text`, `normalize_date`, `extract_horse_no`, `soup`.
- `plan.md` — initial handover roadmap.

## 2026-04-19 — Session 2.7 (Replit via User)

**Forwarded by user from Replit chat.**

Replit confirmed:
- Trainer scraper D1 silent-fail root cause: TrainerData_Scraper.py broke when
  HKJC migrated trainer-ranking page to SPA; parser silently fell through.
- Current `trainer_profiles.csv` contains **1431 duplicate rows** due to
  append-without-dedupe loop.
- `trainers/records/` directory never existed — Replit only persisted the
  2-column aggregated profile, not per-race history.
- Last working scraper commit before bug: **SHA `5dc4752bab17`**.
- GH_TOKEN scopes: `repo`, `workflow`.
- Scheduler: cron UTC 03:30 = HK 11:30 daily.

Phantom horses (Replit-confirmed dead brand codes):
`A111, A112, A113, A117, A118, A120, A121, A123, A124, A125, A127, A128, A129,`
`A133, A135, A136, A137, A138, A139, A141, A144, A145, A146, A148, A149, A150,`
`A152, A156, C408`

Rate limits Replit observed safe at HKJC:
- Trainer 0.25 req/s  · Jockey 0.5 req/s  · Trial 0.4 req/s
- Entry 0.8 req/s     · Horse 0.5 req/s   · Injury 2.5 req/s

## 2026-04-15 — Session 2.6 (User)

User decision: **Option 1** — build Capy pipeline in parallel while user
forwards questions to Replit for handover information. Capy keeps the
feature branch, Replit keeps running main until baseline tag.

## Protocol: adding a new entry

1. Prepend (newest on top) a dated H2 section with attribution.
2. List concrete file changes and decisions.
3. Link to the SHA or PR if available.
4. Append any re-baseline tags to `parity_testing.md` at the same time.
