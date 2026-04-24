# 天喜數據庫 · 實施計劃 & 當前狀態

**最後更新:** 2026-04-24
**版本:** Step-B+ integrity audit landed
**下一個里程碑:** 2026-04-27 soft gate lift → 2026-05-03 earliest Replit stop
**核心原則:** **數據 100% 齊全，唔可以遺漏。**

---

## A · 當前狀態（Backend 邏輯層）

### A1 · Workflow matrix (8 條 auto + 1 disabled)

| # | Workflow | Cron (HK) | Fixture Guard | 狀態 | 近 48h |
|---|---|---|---|---|---|
| 1 | `capy_pool_b_daily.yml` | 02:00 | – | ✅ auto | 2/2 success |
| 2 | `capy_pool_a.yml` | 04:00（gate ≥ 4/27）| 昨日有賽 + ≥4/27 cutover | ⏸ manual-only | 0 run (intentional) |
| 3 | `capy_race_daily.yml` | 賽日 15:30/11:30 UTC | 今日有賽 | ✅ auto | 1/1 success |
| 4 | `capy_entries.yml` | 賽前 03:00 UTC | 明日有賽 | ✅ auto | 1/1 success |
| 5 | `capy_trainer_fix.yml` | 01:00 | 過去 2 日有賽 | ✅ auto | 2/2 success |
| 6 | `capy_fixture_weekly.yml` | 週日 13:15 | – | ✅ auto | 2/2 success |
| 7 | `capy_sanity_daily.yml` | 10:03 | – | ✅ auto | 1/1 success (hotfix 後) |
| 8 | `capy_integrity_audit.yml` | 11:00 | – | ✅ auto (**新**) | 1st run today |
| – | `update-hkjc-scraper.yml.disabled` | – | – | 🗑 deprecated | – |
| – | `elo-v11.yml` | on push to data/* | – | ✅ auto | green |

### A2 · 數據層規模（2026-04-24 實測精準）

| Artefact | 數量 / Size |
|---|---|
| Race days | **886** (2016-2026) |
| 實際 races | **8,361** (distinct date × race_no) |
| Horse-entry rows | **106,004** (每匹馬每場 1 row) |
| Races/day (min-mean-max) | 6 · 9.44 · 11 |
| Horses/race mean | 12.68 |
| 每 race day 5 個 artefact | results · commentary · dividends · sectional_times · video_links |
| Horse profiles | 1,886 (**1,833 retired · 49 inactive · 4 active**) ⚠️ |
| Horse form_records | 1,899 files |
| Trainer profiles | 67 (無 retirement flag) |
| Jockey profiles | 64 (無 retirement flag) |
| Trials | 5,579 rows |
| Fixture dates (2025+2026) | 152 days |
| CSV 總 size | ~88 MB |

### A3 · 已知數據空洞 (2026-04-24 audit)

- 🔴 **1,268 匹現役馬** (D-L 代 debut) 過去 180 日有落場，但**冇 profile**
- 🔴 **1,268 匹 form_records 缺失**
- 🔴 10 個 2025-08 race day artefact 殘缺
- 🟡 67 個 trainer `records/*.csv` 全部 missing
- 🟡 5 個 jockey `records/*.csv` missing
- 🟡 1 個 upcoming race day 冇 entries

詳情見 `audit_reports/integrity_latest.json` + `audit_reports/SUMMARY.md`

### A3 · 自動化覆蓋

- **當前:** 6/7 workflow 全自動（Pool A gate 住）
- **4/27 起:** 7/7 全自動
- **人手介入:** 零（除非 sanity dashboard 亮紅）

---

## B · 已完成里程碑

### B0 · P0 Pivot（2026-04-23, commit `133f714`）
- ✅ 放棄 httpx + SPA parser rewrite，改 reuse Replit 原生 selenium scraper
- ✅ GHA orchestrates `RunAll_Scrapers.py` + `RacingData_Scraper.py`
- ✅ `scraper_utils.py` 加 env override (`CHROMIUM_PATH` / `CHROMEDRIVER_PATH`)
- ✅ 7 個新 workflow 上線：`capy_pool_a/b`, `capy_race_daily`, `capy_entries`, `capy_trainer_fix`, `capy_fixture_weekly`, `capy_sanity_daily`

### B1 · RacingData hotfix（2026-04-24, commit `7e942a1`）
- ✅ 將 Replit 低 RAM flag (`--single-process`, `--max-old-space-size=128`) gated behind `LOW_MEMORY=1` env
- ✅ GHA 7GB runner 唔再 Chrome session crash

### B2 · Fixture calendar rewrite（2026-04-24, commit `1a6c51b` / `fa76a88`）
- ✅ `FixtureCalendar_Scraper.py` 由 Selenium 換 httpx + regex（zero-pad calmonth）
- ✅ Weekly workflow stdlib + httpx 夠，冇 Chrome overhead

### B3 · Step B（2026-04-24, commit `6094164`）
- ✅ `scripts/fixture_guard.sh` shared helper, fail-open
- ✅ Pool A cron + hard cutover guard `TODAY >= 2026-04-27`（dispatch `force=true` 可 bypass）
- ✅ Entries: tomorrow-race window
- ✅ Pool B daily: ±2-day window
- ✅ Trainer: past-2-day window
- ✅ `capy_sanity_daily.yml` 每日 10:03 HK 跑，生成 `reports/SANITY.md`

### B4 · Sanity fix（2026-04-24, commits `8dec668`, `c9f8e1c`）
- ✅ 去除 em-dash（GHA YAML parse 會 silent fail 到 422）
- ✅ 將 multi-line `python3 -c` flatten 做 single-line + single-quote wrap

### B5 · Elo v1.1 self-heal（2026-04-23, commit `a2ac07a`）
- ✅ Summarize step `continue-on-error: true`
- ✅ Runs #4, #5 green

### B6 · Repo rebrand（2026-04-24, 本次）
- ✅ 改名：`HKJC-Horse-Racing-Results` → `tianxi-database`
- ✅ Description: `天喜數據庫 · 香港賽馬 AI 數據平台`
- ✅ Topics: horse-racing / hkjc / hong-kong / data-pipeline / github-actions / elo-rating / sports-analytics / tianxi
- ✅ 舊 URL GitHub 自動 301 redirect（workflow / origin / 下游 integrations 零 break）
- ✅ 新 README.md（面向用戶，清晰運作邏輯）

---

## C · Pending（Integrity-first soft cutover）

### C0 · 核心原則 (非可妥協)

> **「數據係命根，唔可以遺漏。」**
>
> 每個 category 必須 100% 齊全：
> - 每場比賽 5 個 artefact (results / commentary / dividends / sectional_times / video_links)
> - 每匹現役馬必須有 profile + form_records + trackwork
> - 每位現役騎師/練馬師必須有 profile + records
> - Fixture cache 必須涵蓋 current year + upcoming 30 日
> - 試閘 / Entries upcoming 必須新鮮
>
> **Replit VM 唔可以喺 integrity audit 全綠之前停機。**

### C1 · 已發現嘅關鍵 data gap (2026-04-24 audit)

| Category | Severity | Gap | 影響 |
|---|---|---|---|
| horse_profiles | 🔴 critical | **1,268 missing** | 過去 180 日有落場嘅現役馬冇 profile |
| horse_form_records | 🔴 critical | **1,268 missing** | 同上，連 form 都冇 |
| race_artefacts | 🔴 critical | 50 missing | 2025-08 有 10 個 race day 某 artefact 缺 |
| jockey_profiles | 🔴 critical | 1 missing | 1 位現役騎師冇 profile |
| trainer_records | 🟡 warn | 67 missing | Trainer profile 有，但 records/ dir 空 |
| jockey_records | 🟡 warn | 5 missing | 5 位 jockey 冇 records |
| entries_upcoming | 🟡 warn | 1 missing | 1 日 upcoming race 冇 entries |

**Audit tool:** `tools/data_integrity_audit.py`（每日 11:00 HK 自動跑 via `capy_integrity_audit.yml`）
**Output:** `audit_reports/integrity_YYYY-MM-DD.json` + `audit_reports/SUMMARY.md`
**Auto Issue:** Critical 會自動 open Issue 並 label `integrity`

### C2 · 3-phase Soft Cutover（取代 4/27 一刀切）

| Phase | 日期 | Action | Replit VM | GHA |
|---|---|---|---|---|
| **0 (current)** | -2026-04-26 | Replit first-pass 跑緊（集中現役馬 E-L 代）| RUNNING | delta-only |
| **1 (gate lift)** | 2026-04-27 | `capy_pool_a.yml` 硬 gate 自動解；GHA Pool A 日 delta 開始 | **IDLE (standby)** | Pool A auto |
| **2 (parity obs)** | 2026-04-27 到 5/3 | 每日 audit；gap > 0 → 相應 backfill 策略 | IDLE, 隨時可喚醒 | audit + delta + backfill |
| **3 (final gate)** | 2026-05-03 | 連續 7 日 audit 全綠？ → 收 tag `capy-handover-baseline-v2` | **STOP**（只限全綠）| full ops |
| **4 (hard decom)** | ≥2026-06-03 | 再跑 30 日 GHA-only，零 critical → 刪 Replit GH_TOKEN | DELETED | sole |

**停機條件 (必須同時滿足):**
1. `integrity_latest.json`: `overall_severity == "ok"` 連續 7 日
2. `critical_gap_count == 0` 連續 7 日
3. 5/3 前發生過至少 1 個賽日，賽後 audit 通過

**任何一條 fail → Replit VM 唔停**。推遲 7 日再重審。

### C3 · Gap-fill backfill 策略 (by severity + size)

| Critical gap size | 行動 | 誰執行 |
|---|---|---|
| 0 | All green, 冇嘢做 | - |
| 1-50 | GHA 下一次 daily delta 自動修 | 自動 |
| 51-500 | Issue 自動 open，dispatch `capy_pool_a.yml` with `force=true` | 手動觸發 |
| 501-2000 | Dispatch `capy_backfill_gaplist.yml`（feed 具體 horse_no list）| 手動觸發 |
| > 2000 | **喚醒 Replit VM 跑特定 gap-list**，之後 re-audit | 手動 |

### C4 · Replit-side 退場（嚴格 gated）

- [ ] **必要前提:** C2 Phase 3 完成 (audit 7 日全綠)
- [ ] Phase A: Replit Deployment → Stop（但 project 保留）
- [ ] Phase B (≥ Stop 後 7 日): Revoke Replit-side `GH_TOKEN`
- [ ] Phase C (≥ Stop 後 30 日 + GHA 全綠): Archive Replit project（保留 history）
- [ ] Phase D (≥ Stop 後 90 日 + 兩個完整 season): Delete Replit project

### C5 · Audit-driven sanity dashboard integration

`capy_sanity_daily.yml` (每日 10:03 HK) 會讀 `audit_reports/integrity_latest.json`，
將 `overall_severity` / `critical_gap_count` 作 top banner render 入 `reports/SANITY.md`。
亮紅時 dashboard 同 audit 會同時通知。

---

## D · 未來 Roadmap（post-cutover）

### D1 · 數據擴展
- [ ] Elo v2：多因子 model（場地、距離、馬場狀態）
- [ ] Trainer stats 完整 scrape（HKJC SPA stats parsing 現時失敗，silently 得 2 col）
- [ ] `horses/profiles/horse_profiles.csv` dynamic column 正規化
- [ ] 退役馬名尾 `(已退役)` suffix 自動 strip

### D2 · API 層
- [ ] Cloudflare Worker read-only proxy，畀非公開 repo 情況用
- [ ] JSONL export（畀 streaming 用家）
- [ ] Parquet mirror（畀 ML pipeline）

### D3 · 下游產品
- [ ] 前端 dashboard（直 fetch raw CSV）
- [ ] 選馬 AI 助手（基於 Elo + Form + Trackwork signal）
- [ ] Backtest framework（評估 rating model 長線準確度）

---

## E · Runbook 快速索引

| 情境 | 檔案 |
|---|---|
| 新人上手 | [README.md](./README.md) |
| 今日系統健康 | [reports/SANITY.md](./reports/SANITY.md) |
| 歷史 handover 記錄 | [HANDOVER.md](./HANDOVER.md) |
| P0 pivot 決策 log | [CAPY_P0_PIVOT.md](./CAPY_P0_PIVOT.md) |
| 開發日誌 | [BUILD_JOURNAL.md](./BUILD_JOURNAL.md) |
| Data schema 細節 | [DATA_NOTES.md](./DATA_NOTES.md) |
| 本計劃（狀態 + roadmap）| plan.md（本檔）|

### E1 · 手動觸發 workflow

```bash
# Dispatch Pool A（4/27 前 force 模式）
gh workflow run capy_pool_a.yml -f force=true

# Dispatch race day（任何日 manual smoke test）
gh workflow run capy_race_daily.yml

# Dispatch fixture refresh（24 個月）
gh workflow run capy_fixture_weekly.yml
```

### E2 · 查錯順序

1. 查 [`reports/SANITY.md`](./reports/SANITY.md) — 今日狀態一頁睇
2. GitHub Actions tab → 過濾 failed run → 睇 log
3. 如果 Chrome crash → 睇係咪又 trigger 咗 `LOW_MEMORY` 路徑（唔應該）
4. 如果 rate limit → 檢查有冇雙端同時跑（Replit + GHA）
5. 如果 fixture cache stale → 手動 dispatch `capy_fixture_weekly.yml`

---

*本 plan.md 係 living doc。每個里程碑 landed 後應即時更新。*
