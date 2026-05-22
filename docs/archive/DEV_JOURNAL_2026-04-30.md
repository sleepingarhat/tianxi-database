# Dev Journal · 2026-04-30（星期四）

> 承接 2026-04-29 跑馬地 8 場預測 · 解決 D1 sync 斷鏈 · Dark mode 憲法重建 · Frontend 上 CF Pages

## Session goals

1. 修數據管線斷層（D1 最新停喺 04-15，實際 04-29 已出曬賽果）
2. 自動化 D1 sync（跟 capy_race_daily + capy_pool_a 觸發）
3. Dark mode 重建（用戶 2026-04-29 override · 加 AnimatedThemeToggler + WCAG contrast guard）
4. Backend 上 CF Workers · Frontend 上 CF Pages
5. 檢討 2026-04-29 預測準確度
6. 三個 repos 同步 + README 交代

## 時序

### 0400-0530（瞓覺前夜）— P1 數據管線

**P1a · fixture_guard.sh 今日-係-賽馬日 bug**
- 原邏輯：future direction loop `for i in 1..WINDOW`，唔會 check TODAY
- Fix：入 loop 前加 `CANDIDATES=" $TODAY"`
- File：`/tmp/tianxi-db-work/scripts/fixture_guard.sh`

**P1b · D1 sync 自動化**
- 舊 workflow `capy_race_daily` 只 commit CSV 去 tianxi-database，唔 push 上 D1
- 新增 `.github/workflows/capy_d1_sync.yml`：
  - trigger：`workflow_run` after capy_race_daily success + manual dispatch
  - checkout tianxi-database (CSV source) + tianxi-backend (scripts)
  - `npx tsx scripts/import-csv.ts --date $DATE` → 臨時 bulk-local.db
  - `npx tsx scripts/push-delta.ts --since=$SINCE --include=race --out=/tmp/d1-delta`
  - wrangler 按 FK parent 順序逐 chunk push（horses → meetings → races → results → dividends → elo snapshots）
- 配合 capy_pool_a 新增 `capy_d1_sync_pool_a.yml`（同樣套路，30 日 lookback，處理 trackwork / injury / form_records）
- Commits：`ac88ab5` + `378b74d` on tianxi-database@main

**P1c · push-delta.ts critical fix**
- Bug 1：舊版包 `BEGIN;...COMMIT;` wrapper，Cloudflare D1 rejects 顯式 SQL txns（D1 要求用 `state.storage.transaction()` JS API）
- Fix：砍 BEGIN/COMMIT wrapper，emit 純 `INSERT OR REPLACE INTO ${table} VALUES ...;` chunks
- Bug 2：跨 source 嘅 FK — pool-a 表嘅 horse_id 可能唔喺最近 race_results 入面
- Fix：新增 `--include` selector (`race`/`pool-a`/`all`) + `horseRefUnion` UNION 埋 trackwork/injury/form 嘅 horse_id refs
- Commit：`5788a65` on tianxi-backend@main

**P1d · tianxi-backend repo 建立**
- `sleepingarhat/tianxi-backend` 之前只係本地，冇 GitHub remote
- 透過 GitHub REST API + libsodium 加密 secret 建立 private repo
- Set `TIANXI_BACKEND_PAT` secret on tianxi-database（跨 repo checkout 需要）
- 默認 `secrets.GITHUB_TOKEN` 冇跨 repo 權限，workflow 要用 PAT

### 0530-0600 — P2 phantom bugs

- 舊記憶提到 schema_v2.sql views 用錯 column name (`race_no` / `meeting_date`)
- 實際檢查：DDL 用啱（`race_number` / `race_date` / `as_of_date`），只有 comment 有舊名
- Status：no-op，冇嘢改

### 0600-0700 — P3 CF 部署

**Backend (Workers)**：成功 deploy → `https://tianxi-backend.tianxi-entertainment.workers.dev`
- D1 binding 正常
- Routes 全 mount（analyze / meetings / races / horses / silks / chat / lounge）

**Frontend (Pages)**：blocked 於 CF token scope
- Token 有 `D1:Edit` + `Workers:Edit`，但冇 `Cloudflare Pages:Edit`
- API 返 error 10000 "Authentication error"
- 留 remediation 畀用戶：CF dashboard 加 Pages scope

### 0700-0830 — Phase B Dark Mode 憲法重建

**User directive 2026-04-29**: 「A 覆寫舊憲法，但你要確定深淺色模式用色唔好睇唔到啲字」+ AnimatedThemeToggler (圓形擴散動效)

**tokens.css** 加 `:root[data-theme="dark"]` block，所有 tokens 有 contrast 註記：
- `--ink: #f2ece1` · 14.1:1 AAA
- `--ink-soft: #c9bfae` · 10.2:1 AAA
- `--ink-mute: #9a907d` · 6.0:1 AA
- `--paper: #141210` · `--paper-2: #1d1a16`（暖深棕非純黑）
- `--green: #18a355` · 5.1:1 AA · `--red: #ef3d52` · 4.9:1 AA
- `--accent: #d9a547` · 7.9:1 AA · `--accent-strong: #f5c866` · 11.2:1 AAA
- Gold 僅作 decorative（crest bg / underline / beta badge）

**theme.js** 142 行 IIFE controller：
- `localStorage['tx-theme']` ∈ {light, dark, auto}，默認 auto 跟 `prefers-color-scheme`
- `document.startViewTransition` → 圓形 clip-path wipe from click origin
- `prefers-reduced-motion` bypass（fallback 直接切）
- 自動 wire `[data-tx-theme-toggle]` button，update aria-pressed

**Shell**：32×32 toggle button，sun/moon SVG 透過 opacity + rotate 切換；同 dark state CSS rule

**17 個 HTML 頁** 批量注入 script tag + toggle button（404/combo/dashboard/encyclopedia/flow/horse/index/live/login/lounge/pool-odds/predictor/race/results/schedule/value-heatmap/watchlist）

**Contrast audit**：Python WCAG script 跑 30 對 token combo，全部 PASS（light + dark）

### 0830-0900 — 瞓覺中段報告

用戶起身 + 加 CF Pages scope 到 token

### 0900-0930 — Frontend 上線

**Pages project 建立**：REST API POST `/accounts/${acct}/pages/projects` name=`tianxi-site` production_branch=`main`
- Subdomain：`tianxi-site.pages.dev`

**Deploy**：`wrangler pages deploy .` → 23 files uploaded
- URL：`https://tianxi-site.pages.dev`
- Preview：`https://7205f34f.tianxi-site.pages.dev`

### 0930-1000 — 用戶反饋：「網頁仲係之前排版風格」

**發現**：index.html 保留咗舊 hero section + quick-nav 4-tile grid
- Phase B spec：Level-1 純粹 HKJC app 風格（meeting date + races list）
- 我冇 strip hero / quick-nav

**Fix**：edit index.html
- 刪 `<section class="page-head">` hero
- 刪 `<nav class="quick-nav">` 4-tile
- 刪對應 `.quick-nav` CSS（32→0 lines）
- Redeploy → 成功

### 1000-1030 — 檢討 2026-04-29 預測

對 D1 上 race_2026-04-29_HV_1..8 跑 `/api/analyze/top-picks`：

| Race | Top-1 Pred | Actual Win | Top-1 Hit | Top 3 Actual | Top 4 Pred 中幾多 |
|------|------------|------------|-----------|--------------|------------------|
| R1 | #4 (K374) | #4 | ✅ | 4, 3, 5 | 2/3 (#4, #5) |
| R2 | #4 (K283) | #4 | ✅ | 4, 12, 6 | 2/3 (#4, #6) |
| R3 | #10 (K458) | #10 | ✅ | 10, 5, 8 | 2/3 (#10, #8) |
| R4 | #3 (H110) | #3 | ✅ | 3, 11, 1 | 2/3 (#3, #1) |
| R5 | #8 (H356) | #8 | ✅ | 8, 2, 12 | 2/3 (#8, #2) |
| R6 | #4 (K176) | #4 | ✅ | 4, 1, 6 | 2/3 (#4, #1) |
| R7 | #3 (J316) | #3 | ✅ | 3, 8, 2 | 3/3 🎯 |
| R8 | #4 (K451) | #4 | ✅ | 4, 6, 11 | 3/3 🎯 |

**8/8 top-1 命中 = 100%** — 但呢個數字**唔可信**，因為：

**🚨 Data leakage 發現**

1. `scripts/import-csv.ts:659-661` 喺 ingest CSV 後會 UPDATE `horses.total_starts` + `horses.total_wins`，包含 2026-04-29 結果在內
2. `src/routes/analyze.ts:468, 542` 直接讀 `h.total_wins / h.total_starts`（**冇 filter by race date**）
3. 結果：當我 query `/top-picks?raceId=race_2026-04-29_HV_1` 時，getting winRate 已經 include 咗呢場嘅結果 → 贏咗嘅馬 winRate 被人為拉高 → composite score 被抬高 → 變成 top-1

**ELO snapshots** 用 `as_of_date < raceDate` filter 係啱嘅（前提係 snapshots 唔包含 post-race 重算）。

**結論**：8/8 只係 in-sample fit（有 look-ahead bias）· 唔係 out-of-sample 預測準確度。要真正 validate 要：
- A) Pre-race batch 預測：每場開跑前 T-2h 跑 `/top-picks` + 儲起，再同 post-race 對賬
- B) Backend query fix：winRate 要 JOIN race_meetings + `WHERE rm.date < raceDate` 過濾
- B 更易整，A 更全面（可配合 `tools/pre_race_ai_batch.py`）

### 1030-1100 — Push 同 README 收工

- tianxi-backend：commit `5788a65` 已 push（Everything up-to-date）
- tianxi-database：commit `ac88ab5` + `378b74d` 已 push
- 新建 `sleepingarhat/tianxi-site` repo 放 CF Pages 靜態版本
- 更新 3 個 repo 嘅 README.md

## 改動總結

### tianxi-database (public)
- `.github/workflows/capy_d1_sync.yml` NEW
- `.github/workflows/capy_d1_sync_pool_a.yml` NEW
- `scripts/fixture_guard.sh` EDIT（今日係賽馬日 bug）
- `DEV_JOURNAL_2026-04-30.md` NEW（本文件）

### tianxi-backend (private)
- `.gitignore` NEW
- `scripts/push-delta.ts` EDIT（--include + 無 BEGIN/COMMIT + horseRefUnion）
- 全套 source code 首次上 GitHub

### tianxi-site (public · NEW repo)
- `outputs/tianxi-site/**` 全套 23 files
- `assets/theme.js` NEW（AnimatedThemeToggler）
- `assets/tokens.css` dark palette added
- `assets/shell.css` theme-toggle styles
- 17 HTML 頁 injected script + button
- `index.html` Level-1 純 HKJC 風格（strip hero + quick-nav）

## 生產環境 URLs

- Backend: <https://tianxi-backend.tianxi-entertainment.workers.dev>
- Frontend: <https://tianxi-site.pages.dev>
- D1: `tianxi-db` (`aad1636e-869a-43f5-aa95-4a19e3aa5517`)
- D1 latest: `2026-04-29 HV` · 860 meetings · 141 MB

## 待辦 / OPEN 問題

- [ ] **DATA LEAKAGE fix**：`analyze.ts` winRate 用 `horses.total_*` 要改成 date-filtered subquery · 之後重跑 2026-04-29 audit 才算真正驗證
- [ ] Pre-race AI batch workflow：設 T-2h cron 將每場 `/top-picks` snapshot 寫入 `predictions_history` table，之後可以 backtest 真正 accuracy
- [ ] `capy_d1_sync_pool_a` 首次實跑未驗證（等 capy_pool_a 下次 trigger）
- [ ] Frontend visual polish：dark mode 喺 15 個非 Level-1/2/3 頁面需要人手 review
- [ ] 2026-04-29 晨操 / 傷患 CSV 未 push 上 D1（要 capy_pool_a 跑）

## Lessons learned

1. **D1 唔接受 `BEGIN;...COMMIT;`** — 要用 JS transaction API。任何 bulk INSERT script 都要小心。
2. **GHA 跨 repo checkout 要 PAT** — 默認 `GITHUB_TOKEN` 限於當前 repo。
3. **Cumulative stat on entity table = leakage trap** — `horses.total_wins` 呢類 denormalized counter 會喺 ingest 新 race result 之後即時更新，令後續 query 帶咗「後見之明」。要就係每次 query 都 re-aggregate from race_results with date filter，要就係 snapshot at ingest time。
4. **CF Pages 同 Workers 係兩個獨立 token scope** — 用同一個 token 要兩個 permission 都加。
5. **Contrast audit 應該係 design system 組件** — 唔係事後 QA。可以搞成 build-time 失敗條件。
