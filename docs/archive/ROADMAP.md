# 天喜 TIANXI · ROADMAP

Last updated: **2026-04-29**

> 本文件係 single source of truth，列明系統現狀、缺口、運行手冊、以及 Phase 1 → Phase 2 嘅過渡條件。

---

## 狀態總覽

| 層 | 模組 | 狀態 | 備註 |
|---|---|---|---|
| 資料 | HKJC results scraper | 🟡 修復中 | Nix path bug 已 patch · 等 merge + workflow_dispatch 跑 backfill |
| 資料 | HKJC entries scraper | ✅ 運作中 | `capy_entries.yml` cron（HK 20:00 Mon/Tue/Sat）正常 |
| 資料 | 馬匹 / 騎師 / 練馬師 / 試閘 scrapers | ✅ 運作中 | 各 workflow 獨立 |
| 運算 | ELO v1.1 engine | ✅ | `scripts/elo/compute_v11.ts` · 單軸 |
| 運算 | ELO v1.2 engine（三軸時間衰減） | ✅ | `scripts/elo/compute.ts` · horse/jockey/trainer 分開 · K 32→24→16 · halflife 365d |
| 運算 | Composite score | ✅ | `0.7 × horseElo + 0.2 × jockeyElo + 0.1 × trainerElo`（未 backtest calibration） |
| 運算 | 7 個 per-race 因子 | ✅ | distanceFit / goingFit / drawBias / weightDelta / conditionFit / injuryFlag / jtComboFit · 位於 `src/routes/analyze.ts:220-445` |
| 運算 | Plackett-Luce softmax | ✅ | scale=100 · pWin / pTop3 / valueDelta |
| 運算 | AI explain（human-readable breakdown） | ✅ | `/api/analyze/explain` |
| 運算 | Backtest / calibration | ❌ | 待 P5 · 需完整歷史數據 |
| 管線 | GHA `capy_race_daily` | 🟡 修復中 | cron 設 HK 23:30 · sanity check 已加 · 等 merge |
| 管線 | GHA `capy_entries` | ✅ | |
| 管線 | GHA `elo-post-race`（新） | ✅ | workflow_run 觸發 · 自動 recompute + D1 ingest trigger |
| 管線 | D1 incremental ingest | 🟡 | workflow 存在於 `d1-incremental-ingest.yml`（或 replit 側）· 未驗證 post-race 鏈式觸發 |
| 前端 | tianxi-v2 (React + Vite) shell | ✅ | 3 pages (Home/Race/Horse) · 19 Magic UI 組件 · flat light-only |
| 前端 | API client layer | ✅ | `src/lib/api.ts` + `src/lib/hooks.ts` · env-gated mock fallback |
| 前端 | 真 API 接駁（production） | 🟡 | 設 `VITE_USE_MOCK=0` + `VITE_API_BASE_URL` 即切換 · 尚未 end-to-end 驗證 |
| 前端 | 深淺色 toggle / 4-card BorderBeam / inverse CTAs / 高清綵衣 | ❌ | 待 post-P6 frontend polish |
| 部署 | tianxi-backend (Cloudflare Workers + D1) | ✅ | `wrangler deploy` · endpoints 齊 |
| 部署 | tianxi-frontend v1 (Next.js @ Vercel) | ✅ | 舊版 · 逐步 deprecate |
| 部署 | tianxi-v2 (target: Vercel / CF Pages) | 🟡 | 未部署 · local dev only |
| 治理 | GitHub push（2 repos） | 🟡 | 等你提供 PAT 或本地 git push |
| 治理 | Monitoring / alerts | ❌ | workflow 失敗無 Slack/Email 通知 · 待加 |

---

## 修復歷史（2026-04-29 session）

1. ✅ `hkjc-data/RacingData_Scraper.py`：Nix path 硬編碼 → env-overridable with fallback chain
2. ✅ `hkjc-data/.github/workflows/capy_race_daily.yml`：加 sanity check · 如果 scraper 失敗 + CSV mtime 無變 → fail loud
3. ✅ `hkjc-data/.github/workflows/elo-post-race.yml`（**新**）：workflow_run 觸發 · 自動跑 `compute.ts --engine v12` · commit reconcile.db · 鏈式 dispatch `d1-incremental-ingest`
4. ✅ `tianxi-v2/src/lib/api.ts`（**新**）：typed fetch wrapper · ApiError · 4 個 endpoint
5. ✅ `tianxi-v2/src/lib/hooks.ts`（**新**）：`useNextMeeting` / `useRace` / `useHorseExplain` · loading/error/refetch
6. ✅ `tianxi-v2/src/data/mock.ts`：`loadMeeting` + `silksUrl` 改為 env-gated dispatcher
7. ✅ `tianxi-v2/src/vite-env.d.ts`：補 `ImportMetaEnv` 類型
8. ✅ `tianxi-v2/.env.example`：VITE_USE_MOCK / VITE_API_BASE_URL 配置範例

---

## Runbook

### A · 2026-04-16 → 2026-04-28 backfill（push 後第一件事）

**前提**：本 ROADMAP.md + scraper patch 已 merge 到 `sleepingarhat/tianxi-database` main branch。

1. 在 GitHub UI → Actions → **Capy Race Day — RacingData Results** → Run workflow on `main`
2. 每次 trigger 只會跑當日 → 要手動 trigger 3 次：
   - 一次觸發 → scraper 會自動掃描缺失日 · 理論上一口氣補齊
   - 如只補到最近一日，需要加 `workflow_dispatch` input `backfill_days`（本 patch 未加，後續改）
3. 跑完後 → `elo-post-race` workflow 應自動 fire → 生成新 reconcile.db → 觸發 D1 ingest
4. 驗證：`curl https://tianxi-api.your-account.workers.dev/api/meetings/smart/current | jq '.date'` 應返回 `2026-05-xx`（下一場未來日），而不是 `2026-04-15`

### B · 前端切到真後端

```bash
cd outputs/tianxi-v2
cp .env.example .env.local
# 編輯 .env.local：
# VITE_USE_MOCK=0
# VITE_API_BASE_URL=https://tianxi-api.your-account.workers.dev
npm run dev
```

E2E 檢查清單：
- [ ] Home 載入 · 顯示下一場 meeting date（不再係 2026-04-29 mock）
- [ ] Race 頁載入 · 排位表 12-14 匹馬齊 · AI 預測頭三 + pTop3
- [ ] Horse 頁載入 · factorBreakdown 7 個因子 non-null · comment 有中文解釋

### C · GitHub push runbook

```bash
# 1. Setup credentials (once)
gh auth login --with-token < ~/my_gh_pat.txt

# 2. tianxi-database
cd hkjc-data
git add RacingData_Scraper.py \
        .github/workflows/capy_race_daily.yml \
        .github/workflows/elo-post-race.yml
git commit -m "fix(scraper): resolve Nix path via env override + add post-race ELO chain"
git push origin main

# 3. tianxi-frontend (new v2)
cd ../outputs/tianxi-v2
# First time: git init + remote add
git add -A
git commit -m "feat(v2): Magic UI shell + env-gated API client + 3-level nav"
git push origin main

# 4. Trigger backfill (see Runbook A)
gh workflow run capy_race_daily.yml --repo sleepingarhat/tianxi-database --ref main
```

### D · 後續 frontend polish（user 2026-04-29 directive）

等 C 執行後做：

1. `pnpm dlx shadcn@latest add @magicui/animated-theme-toggler` — 圓形擴散 dark/light toggle（但注意憲法規定 light-only，**呢一步要同用戶確認**：係咪放棄 2026-04-28 「dark mode DELETED」憲法？）
2. `BorderBeam` 包 4 個 stat 卡（場次 / 參賽馬 / AI 信心 / 天喜平台特色）
3. 「查看全部9場」改 solid 黑底白字 / 「天喜 AI 預測」白底黑字（dark mode 鏡射反轉）
4. 「天喜 AI 預測」加 `<DiaTextReveal>`（但注意：呢條 CTA 本身要 plain，DiaTextReveal 可能動感太強 → 二次確認）
5. 「立即開始 · Beta 免費」/「加入心水」移除 shimmer / ripple 效果
6. 「決定權永遠交返俾你」改用 `<AnimatedGradientText>`
7. 高清綵衣：HKJC 官方只提供 GIF（低清）· 解決方案：
   - 方案 A · 用 `<Silks>` component 升級做 SVG · 由 `/api/silks/:code.svg` 返回 backend-rendered colored pattern · 高解析
   - 方案 B · Scrape HKJC `color_*.png`（如存在）代替 `.gif`
   - 方案 C · Upscale via image-gen service（成本較高）
   - 建議方案 A，需要 backend 新 endpoint · 可作為獨立任務

---

## Phase 1 → Phase 2 轉化閘

（參考 `MEMORY.md · Launch model 2026-04-25`）

Trigger 條件（所有皆滿足）：
- [ ] DAU ≥ TBD（user 決定）
- [ ] 註冊用戶 ≥ TBD
- [ ] ELO + factor backtest hit rate ≥ baseline（市場 favorite win rate 約 32-35%；TIANXI top-1 win rate 目標 ≥ 40%）
- [ ] Frontend 接真 API E2E stable ≥ 14 日

Phase 2 工作（未 scheduled）：
- [ ] Calibrate ELO composite weights via backtest (grid search on 0.6-0.8 / 0.15-0.25 / 0.05-0.15)
- [ ] Calibrate factor bonus weights（目前每 factor equal weight summed → 可能 overweight drawBias / underweight conditionFit）
- [ ] Token cost separation UI（靜態 free / AI chat rate limit / DIY slider free）
- [ ] Pricing page（凍結 tiers unfreeze · 或重設）

---

## Security / Governance reminders

- ❌ **NEVER** 展示「投注金額」「派彩估算」「bet slip」— 平台 scope 紅線
- ✅ 可以展示：所有彩池賠率 / 投注分佈 / 組合概率排名 / 值博度 + disclaimer
- ❌ **NEVER** 用 emoji（user 2026-04-24 指令）
- ✅ 所有 3 頁統一 flat light-only design（user 2026-04-28 指令）
  - ⚠️ 若要加 theme toggle，需 user 確認是否覆寫呢條憲法

---

## Open questions / requires user input

1. **Theme toggle 是否違反 light-only 憲法？** user 今日要求加 animated-theme-toggler · 要確認是否覆寫 2026-04-28 「dark mode DELETED」directive
2. **GITHUB_TOKEN / PAT**：push 兩個 repo 需要
3. **Cloudflare API token**：tianxi-backend 重新 deploy（如 D1 schema 要 migration）需要
4. **Backfill 4/16 → 4/28**：只能喺 GHA runner 跑 · 你 push + trigger workflow
5. **高清綵衣方案**：A/B/C 揀邊個
