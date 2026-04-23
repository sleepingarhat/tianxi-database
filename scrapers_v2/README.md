# Scrapers v2 (Capy)

**Status**: Feature branch `capy/scraper-v2` · continuously evolving
**Owner**: Capy (天喜 AI agent), taking over from Replit-based Selenium scraper
**Deploy target**: GitHub Actions Cron (free tier)

---

## Why v2

Replit scraper uses Selenium + Chromium for 12/13 endpoints. After discovery:

| Endpoint | Replit approach | v2 approach | Speedup |
|---|---|---|---|
| LocalResults / DisplaySectionalTime / Horse profile / Form / Trackwork / Jockey records / Trainer profile + records / Trial results / Entries | Selenium + Chromium | **httpx (async)** | 10-20x per req, 50-100x with concurrency |
| Trainer-ranking / Jockey-ranking (Next.js SPA) | Selenium | **Playwright (weekly ID refresh only)** | N/A — run ~1x/week |
| Injury (ovehorse) | requests (already httpx) | httpx | — |

**Net expected**：30-50x throughput vs Replit; Pool A 3000 馬 ~30 min instead of 42 hr.

## Design Rules

1. **100% output compatibility** with Replit CSV schema (column name + order + format)
2. **Data Independence Principle** — never ingest HKJC derived outputs (odds tiers, AI picks, etc.)
3. **Parity-gated cutover** — v2 writes to `staging/`, diff vs Replit, 0 diff = promote
4. **Idempotent + resumable** — all scrapers can be safely killed + restarted
5. **Rate limit friendly** — token bucket (default 10 req/s per host), User-Agent spoof

## Directory Layout

```
scrapers_v2/
├── http_client/      httpx async client + retry + throttle
├── browser_client/   Playwright for SPA (trainer-ranking only)
├── parsers/          BeautifulSoup → dict (pure functions, testable)
├── shared/           utils + lifecycle + git_sync
└── orchestrator/
    ├── daily/        daily race day + entries
    ├── pool_a/       form_records + horse profile
    └── pool_b/       trackwork + injury
```

## Running Locally

```bash
# Install
pip install -r scrapers_v2/requirements.txt

# Single race day
python -m scrapers_v2.orchestrator.daily.scrape_race_day --date 2026-04-22

# Trainer fix (the D1 bug)
python -m scrapers_v2.orchestrator.daily.scrape_trainers --refresh-ids

# Entries
python -m scrapers_v2.orchestrator.daily.scrape_entries --date 2026-04-22 --course HV
```

## GitHub Actions Workflows

| Workflow | Cron | Purpose |
|---|---|---|
| `capy_trainer_fix.yml` | `*/6 * * *` (every 6 hr) | Trainer profile + records refresh |
| `capy_race_daily.yml` | `0 2,13,21 * * *` (3x/day) | Daily race result + dividends + sectional |
| `capy_entries.yml` | `*/20 * * * *` | Entries race-day polling |
| `capy_trainer_ids.yml` | `0 3 * * 1` (weekly Monday 3am HKT) | Playwright ID refresh |
| `capy_pool_a.yml` | `0 */3 * * *` | Form + profile backfill batch |
| `capy_pool_b.yml` | `30 */6 * * *` | Trackwork + injury batch |
| `capy_git_sync.yml` | (embedded in each above) | Git commit + push after batch |

## CSV Schema Pinning

All parsers must output CSV with these exact column orders (ported from Replit):

- `data/YEAR/results_*.csv` — 25 cols (see `parsers/race_results.py`)
- `horses/form_records/form_*.csv` — 21 cols (see `parsers/horse_form.py`)
- `horses/profiles/horse_profiles.csv` — **DYNAMIC in Replit; v2 pins 20+ columns by name match** (see `parsers/horse_profile.py`)
- `jockeys/records/jockey_*.csv` — 19 cols (see `parsers/jockey.py`)
- `trainers/records/trainer_*.csv` — **new stable schema** (Replit had dynamic)
- `horses/trackwork/trackwork_*.csv` — 7 cols
- `horses/injury/injury_*.csv` — 4 cols
- `trials/trial_results.csv` — 18 cols

See `docs/capy/csv_schemas.md` for full spec.

## Session / Handover Log

- 2026-04-22 Session 2.9：feature branch created，phase A foundation landed
- 2026-04-23 (planned)：parity test framework + cutover decision
- 2026-04-24 (planned)：Replit stops, full handover to GHA

See `docs/capy/handover_log.md`.
