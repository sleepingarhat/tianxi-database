# Dev Journal · 2026-04-29（星期三 · 跑馬地）

> 將來借鑒做足球賽事，呢份日誌要夠 step-by-step 重建得返整個 pipeline。

## Session goals

1. 出今日 9 場預測
2. 修 scraper 4/15 卡住問題
3. 建立真 frontend（tianxi-v2）+ 接真 API
4. 將代碼 push 上 GitHub 兩個 repo（database / frontend）

## 時序

### 0900 — 環境 survey

發現：
- `tianxi-backend/` 已存在 · Hono + D1 · routes + services 齊
- `hkjc-data/` scraper 6 個 Python 檔 + .github/workflows 7 個
- `outputs/tianxi-v2/` 新 React 項目 shell
- Sandbox 無 Chromium / Chrome · Mac bridge 未連接 · gh 未 auth

### 1000 — 輸出 2026-04-29 預測

用 `browser` CLI scrape HKJC racecard 頁（9 場）· 用 reconcile.db（截至 4/15 snapshot）跑 ELO v12 · Plackett-Luce softmax → 寫入 `outputs/predictions_2026-04-29.md` + `.json`。

**caveat**：ELO 落後 14 日 · 2 週內打過仗嘅馬匹 rating 未更新。

### 1100 — Frontend v2 UI shell 完成

19 Magic UI 組件全部接入 · 3 pages E2E walkthrough 通過 · TypeScript 0 error · preview URL export 成功。

### 1200 — 用戶問 8 個硬問題

user: 「ELO 100%？因子完成？自動更新？4/15 解決？DB 完整？前端接駁？」

我給出悲觀評估（基於過時記憶），話大部分未做。

**錯誤**：我嘅 MEMORY.md 停喺 2026-04-28 · backend 其實已進化。

### 1300 — 實地 verify 後大翻盤

查 `src/routes/analyze.ts:220-445` → 發現 7 個 factor 已 implemented（`distanceFit / goingFit / drawBias / weightDelta / conditionFit / injuryFlag / jtComboFit`）· ELO v11 + v12 engines 齊 · GHA workflows 7 個齊。

真正缺口縮水到：
- Scraper Nix path bug（~5 行 patch）
- Workflow silent-failure masking（sanity check）
- Frontend API client（~250 LOC）
- Journal + git push

### 1400 — 修 + 建

**Commits（logical units）**：

1. `fix(scraper): resolve CHROMIUM_PATH via env with fallback chain`
   - `hkjc-data/RacingData_Scraper.py` L23-24 改做 `_resolve()` helper

2. `fix(ci): add sanity check to capy_race_daily workflow`
   - `hkjc-data/.github/workflows/capy_race_daily.yml` · 加 pre/post mtime snapshot · 如 scraper 失敗 + CSV 無變 → fail loud

3. `feat(ci): elo-post-race auto-trigger workflow`
   - 新 `hkjc-data/.github/workflows/elo-post-race.yml`
   - `workflow_run` 觸發自 `Capy Race Day` · 自動跑 `compute.ts --engine v12` · commit reconcile.db · chain dispatch `d1-incremental-ingest`

4. `feat(v2): typed API client + hooks + env config`
   - 新 `outputs/tianxi-v2/src/lib/api.ts`：`fetchNextMeeting` / `fetchRace` / `fetchHorseExplain` + `ApiError`
   - 新 `outputs/tianxi-v2/src/lib/hooks.ts`：`useNextMeeting` / `useRace` / `useHorseExplain`
   - 新 `outputs/tianxi-v2/.env.example` · `src/vite-env.d.ts`
   - 改 `src/data/mock.ts`：`loadMeeting` / `silksUrl` 改做 env-gated dispatcher

5. `docs: ROADMAP.md + DEV_JOURNAL_2026-04-29.md`

---

## 關鍵設計決策

### DD-1 · Scraper env resolution 策略

**Context**：Nix path 硬編碼只 work on user 原 Replit 環境 · GHA / local Mac / sandbox 全失敗。

**Options**：
- A · 環境變數 only（`os.environ["CHROMIUM_PATH"]`）：硬要求每個 caller export
- B · 環境變數 + fallback：env 優先、否則試常見系統路徑、最後 Nix default
- C · 用 `webdriver-manager` 自動下載：加依賴 · 離線不 work

**選 B**。理由：(1) GHA 現有 `Export browser paths` 步驟會生效；(2) 用戶本地 Mac 唔使改 env 都 work；(3) Nix 環境保持 backward compat。

### DD-2 · Post-race ELO 觸發方式

**Options**：
- A · Cron 獨立（e.g. HK 00:00 每日跑一次）：可能喺 scraper 還未完成時跑
- B · `workflow_run`（我選）：chain 觸發 · GHA 原生 support · 只 scraper 成功先跑
- C · 外部 webhook：多一個 infra 依賴

**選 B**。`workflow_run` 有內建 `conclusion: success` 判斷 · 失敗自動 skip · 配合 scraper workflow 嘅新 sanity check 形成閉環。

### DD-3 · 前端 mock/real dispatcher 位置

**Options**：
- A · 改 pages 用新 hooks：改動面大（3 files）
- B · 喺 `mock.ts` 做 env gate（我選）：pages 唔使改 · 保留現有 `loadMeeting()` 接口
- C · 另起 `provider.ts`：多一個 module

**選 B**。理由：(1) pages 已經過 QA，唔想重碰；(2) `mock.ts` 本身就係 data source entrypoint · 改呢度符合 SRP；(3) 測試時只需 flip 一個 env var。

副作用：`mock.ts` 名不副實（唔只係 mock）· 理想改名 `data-source.ts`，但本次唔想擴大 blast radius · 留 P6 之後 polish。

### DD-4 · API endpoints 選擇

從 tianxi-backend 可用 endpoints 中揀：
- ✅ `/api/meetings/smart/current` — 下一 meeting + 所有 races
- ✅ `/api/analyze/top-picks?raceId=X` — composite ELO + factor bonus + pWin/pTop3
- ✅ `/api/analyze/explain?raceId=X&horseId=Y` — factor breakdown + comment
- ❌ **未用**：`/api/odds`（odds 走勢）· `/api/horses/:code`（馬匹 profile）· `/api/chat`（AI chat）

理由：v2 現階段只覆蓋 Home/Race/Horse 3 頁 · 其他 endpoints 對應嘅 UI 仲未建 · 等對應頁完成再接。

---

## 未解決 + ready-to-execute backlog

### 立即能做（push + GHA 可完成）

- [ ] Backfill 4/16 → 4/28（一個 `workflow_dispatch` 觸發）
- [ ] ELO recompute through 4/28（post-race workflow 會自動鏈式）
- [ ] D1 ingest 新 reconcile.db（chain dispatch）

### 要人決定

- [ ] Theme toggle 是否覆寫 light-only 憲法？
- [ ] 高清綵衣：SVG render / PNG scrape / AI upscale 揀邊個

### Phase 2 深水

- [ ] Backtest 2 年歷史 → calibrate `0.7 / 0.2 / 0.1` ELO weights
- [ ] Grid search per-factor weights（目前 equal-weighted sum · 應 learned）
- [ ] Pricing tier unfreeze

---

## 借鑒筆記（將來做足球賽事時參考）

1. **Scraper 要 env-overridable from day 1**。Nix/Replit/Docker/GHA 各環境路徑唔同 · 硬編碼必炒。
2. **Silent failure 係最貴嘅 bug**。GHA `continue-on-error:true` + `|| echo "no data"` 呢種 pattern 會令 pipeline 斷 2 週都冇人知。必加 sanity check + fail loud + Slack/Email alert（後者未加 · 補欠）。
3. **ELO 多軸優於單軸**。球員 / 教練 / 主客軸分開 decay，再做 weighted composite，比單一球員 rating 穩得多。
4. **Plackett-Luce 一次模型多個名次 (win/place/show)**。賽馬 = 排名 top-K 問題 · 足球 = 勝負平 + 進球數 · 前者直接用 PL softmax 最乾淨。
5. **「Top-1 可以 rating 低於 Top-2」係正確行為**。因子調整後嘅 final score 先決定排名 · UI 要有能力展示「ELO 低但場次適應高」嘅雙行解釋 · 否則用戶覺得系統矛盾。
6. **前端 early 分離 mock / real provider**。有 env gate 就可以做 demo + production 共用一套 UI code · 唔會因為 backend 未 ready 阻住 UX 疊代。
7. **憲法（constitutional spec）要定期 sync 返去長期記憶**。今日我嘅 MEMORY.md 過時 2 日 · 差啲畀錯誤前提出錯誤 roadmap。每次大 decision 即時更新 memory file。
