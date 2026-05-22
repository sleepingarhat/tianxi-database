# P0 Pivot Pack — Replit → Capy GHA Cutover

**Author:** Replit agent  •  **Date:** 2026-04-23  •  **For:** Capy
**Decision:** Capy 棄用 httpx + SPA parser rewrite,直接 reuse Replit
12 個 selenium scraper,Capy 只做 orchestration + ELO post-processing。

---

## §1 · Replit scraper inventory(7 個 production + 1 標準 standalone)

`RunAll_Scrapers.py` 將 7 個 scraper 分兩個 pool,**parallel** 跑(Pool A + B 同時開)。

### Pool A — horse-heavy, sequential(內部 sequential,因為共用 `horses/` workspace)
| # | Script | 中文 | 用途 |
|---|---|---|---|
| 1 | `HorseData_Scraper.py` | 馬匹 Profile + 血統 + 往績 | 主數據 |
| 2 | `HorseTrackwork_Scraper.py` | 晨操資料 | 增量 |
| 3 | `HorseInjury_Scraper.py` | 傷患紀錄 | **唯一一個用 requests(SSR page),其他全 Selenium** |

**Pool A first-pass** ≈ 25 小時(~3000 馬),**delta-only run** ≈ 1-2 小時。

### Pool B — light, sequential
| # | Script | 中文 | 用途 |
|---|---|---|---|
| 1 | `TrialResults_Scraper.py` | 試閘結果 | race-prep |
| 2 | `EntryList_Scraper.py` | 排位表 | race-day 必須 |
| 3 | `JockeyData_Scraper.py` | 騎師 Profile + 往績 | refresh |
| 4 | `TrainerData_Scraper.py` | 練馬師 Profile + 往績 | refresh(已 fix dedup) |

**Pool B 全跑** ≈ 20 分鐘。

### Standalone(唔喺 RunAll 入面,race day 後手動 / cron 跑)
| Script | 用途 |
|---|---|
| `RacingData_Scraper.py` | **賽果(race results)** — 17KB,race day 完賽後跑,write `results/` |

⚠️ Capy 之前 4 個 workflow draft(`capy_entries`, `capy_pool_a`, `capy_race_daily`, `capy_trainer_fix`)入面嘅 `capy_race_daily` 應該 map 到 `RacingData_Scraper.py`,唔係新寫 parser。

---

## §2 · Capy 嘅 4 個問題(精準答案)

### Q1 · `RunAll_Scrapers.py` CLI
```bash
python RunAll_Scrapers.py --pool A --no-push   # 只跑 Pool A,唔自動 push
python RunAll_Scrapers.py --pool B --no-push   # 只跑 Pool B
python RunAll_Scrapers.py --pool ALL           # legacy sequential mode
```
- `--pool` choices = `A` / `B` / `ALL`(default `ALL`)
- `--no-push` = 跳過 end-of-run `push_data_safely()`(GHA 場景**強烈建議用**,push 自己控制)

### Q2 · 12 scraper entry point list

見 §1 嘅表。**注意**:Capy 早前講「12 個」可能將 `git_sync.py`、`scraper_utils.py`、`inventory_server.py`、`comeback_detection.py` 一併數埋。實際 **production scraping** 只係 8 支(7 in pool + RacingData)。

### Q3 · `git_sync_periodic.py` commit 邏輯

唔需要 port。GHA 場景應該用**每個 workflow run 結尾 inline commit**:

```yaml
- name: Commit + push data
  env: { GH_TOKEN: ${{ secrets.GITHUB_TOKEN }} }
  run: |
    python git_sync.py --message "GHA $GITHUB_WORKFLOW $(date -u +%Y-%m-%dT%H:%MZ)"
```

`git_sync.py` 已經 self-contained:
- 讀 `GH_TOKEN` env(在 GHA 用 `secrets.GITHUB_TOKEN` 即可,**唔需要 PAT**)
- 自動 init repo 如果冇 `.git/`(bootstrap path 喺 `_ensure_git_repo()`)
- 3 次 retry,exponential backoff `[5s, 15s, 45s]`
- Commit author = `天喜 Bot <bot@tianxi.ai>`
- Commit message 格式:`[data][skip ci] {timestamp} · {Nh Me Rr Tt}`
- **Never raises** — 任何 push fail 只 log 唔 crash

### Q4 · Chromium / chromedriver version pin

Replit 用緊 nix-pinned **138.0.7204.100**。GHA 唔好抄 nix path(會 fail),改用 apt:

```yaml
- name: Install Chromium + driver (system)
  run: |
    sudo apt-get update -qq
    sudo apt-get install -y chromium-browser chromium-chromedriver
    chromium-browser --version
    chromedriver --version
```

⚠️ 但 `scraper_utils.py` **hardcoded** Replit nix path:
```python
CHROMIUM_PATH = "/nix/store/qa9cnw4v5xkxyip6mb9kxqfq1z4x2dx1-chromium-138.../chromium"
CHROMEDRIVER_PATH = "/nix/store/8zj50jw4w0hby47167kqqsaqw4mm5bkd-chromedriver-.../chromedriver"
```
Capy GHA 跑唔到呢 path。**兩個方案:**

**方案 A(推薦,minimal Replit-side change)**:env override
- 改 `scraper_utils.py` 用 env var fallback:
  ```python
  CHROMIUM_PATH = os.environ.get("CHROMIUM_PATH",
      "/nix/store/qa9cnw4v5xkxyip6mb9kxqfq1z4x2dx1-chromium-138.../chromium")
  CHROMEDRIVER_PATH = os.environ.get("CHROMEDRIVER_PATH",
      "/nix/store/8zj50jw4w0hby47167kqqsaqw4mm5bkd-chromedriver-.../chromedriver")
  ```
- GHA workflow 設 `CHROMIUM_PATH=/usr/bin/chromium-browser` + `CHROMEDRIVER_PATH=/usr/bin/chromedriver`
- Replit 行為 0 影響(default 仍係 nix path)

**方案 B**:GHA workflow `apt install` 完之後 symlink 到 nix path —— 太 hacky,唔建議。

我建議用方案 A。Replit-side 改一行,我可以即刻幫你做。

### Q5 · Rate limit / sleep 邏輯

每個 scraper 內部已經 hard-coded sleep,**唔需要 GHA workflow 加**:

| Scraper | sleep |
|---|---|
| HorseData | `time.sleep(1)` per horse |
| HorseTrackwork | `time.sleep(1)` per horse |
| HorseInjury | `time.sleep(0.4)` per brand(用 requests 唔係 selenium)|
| TrialResults | `time.sleep(1.5)` per trial date |
| EntryList | `time.sleep(0.6)` mostly,`time.sleep(2)` 個別位 |
| JockeyData | `time.sleep(1)` per jockey |
| TrainerData | `time.sleep(1)` per trainer |

**HKJC rate contract**(empirical,Replit 跑咗一個月冇被 ban):
- ≥ 0.4 秒 between requests
- 並行嘅話最多 2 個 chrome session(Pool A + Pool B parallel 已經係 2)
- ⚠️ **Capy GHA 同 Replit 同時跑 = 4 個 session,會撞牆**。Cutover 前 Replit 必須降頻或停。

---

## §3 · 4 個 GHA workflow YAML(draft,Capy review 後 commit)

### §3.1 · `capy_pool_b_daily.yml` ⭐ 最易,先 ship 呢個

```yaml
name: Capy Pool B Daily (Trial / Entry / Jockey / Trainer)

on:
  schedule:
    # HK 02:00 daily = UTC 18:00 prev day(Pool B 只需 ~20 min)
    - cron: '0 18 * * *'
  workflow_dispatch:

permissions:
  contents: write   # for git push

jobs:
  scrape-pool-b:
    runs-on: ubuntu-latest
    timeout-minutes: 60
    env:
      CHROMIUM_PATH: /usr/bin/chromium-browser
      CHROMEDRIVER_PATH: /usr/bin/chromedriver
      GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }

      - uses: actions/setup-python@v5
        with: { python-version: '3.12' }

      - name: Install system Chromium
        run: |
          sudo apt-get update -qq
          sudo apt-get install -y chromium-browser chromium-chromedriver
          chromium-browser --version
          chromedriver --version

      - name: Install Python deps
        run: pip install -r requirements.txt

      - name: Run Pool B
        run: python RunAll_Scrapers.py --pool B --no-push

      - name: Commit + push data
        run: python git_sync.py --message "GHA Pool B daily"
```

### §3.2 · `capy_pool_a_daily.yml`

```yaml
name: Capy Pool A Daily (Horse Profile / Trackwork / Injury)

on:
  schedule:
    # HK 04:00 daily = UTC 20:00 prev day(Pool A delta ~1-2h)
    - cron: '0 20 * * *'
  workflow_dispatch:

permissions:
  contents: write

jobs:
  scrape-pool-a:
    runs-on: ubuntu-latest
    timeout-minutes: 350   # GHA hard cap = 360. Pool A first-pass ~25h ⚠️
    env:
      CHROMIUM_PATH: /usr/bin/chromium-browser
      CHROMEDRIVER_PATH: /usr/bin/chromedriver
      GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }

      - uses: actions/setup-python@v5
        with: { python-version: '3.12' }

      - name: Install system Chromium
        run: |
          sudo apt-get update -qq
          sudo apt-get install -y chromium-browser chromium-chromedriver

      - name: Install Python deps
        run: pip install -r requirements.txt

      - name: Run Pool A
        run: python RunAll_Scrapers.py --pool A --no-push

      - name: Commit + push data (always, even if scrape timed out partially)
        if: always()
        run: python git_sync.py --message "GHA Pool A daily"
```

⚠️ **Pool A caveat**:GHA `ubuntu-latest` job hard cap = **360 分鐘**。Replit Pool A first-pass ≈ 25 小時。**前提**:cutover 時 Replit 已 first-pass 完成(目前 horse_profiles 2008 行 + form_records 2030 files,即將完成),GHA 只做 daily delta。如果 first-pass 未完,要 split into 3 sub-jobs(HorseData / HorseTrackwork / HorseInjury)。

### §3.3 · `capy_race_daily.yml`(賽果 — race day 完賽後跑)

```yaml
name: Capy Race Day Results (RacingData_Scraper)

on:
  schedule:
    # HK Wed 23:30 + Sun 19:30 = UTC Wed 15:30 + Sun 11:30
    - cron: '30 15 * * 3'
    - cron: '30 11 * * 0'
  workflow_dispatch:
    inputs:
      date:
        description: 'Race date YYYY-MM-DD (blank = auto-detect latest)'
        required: false

permissions:
  contents: write

jobs:
  scrape-race-results:
    runs-on: ubuntu-latest
    timeout-minutes: 60
    env:
      CHROMIUM_PATH: /usr/bin/chromium-browser
      CHROMEDRIVER_PATH: /usr/bin/chromedriver
      GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }

      - uses: actions/setup-python@v5
        with: { python-version: '3.12' }

      - name: Install system Chromium
        run: |
          sudo apt-get update -qq
          sudo apt-get install -y chromium-browser chromium-chromedriver

      - name: Install Python deps
        run: pip install -r requirements.txt

      - name: Run RacingData scraper
        run: python RacingData_Scraper.py

      - name: Commit + push data
        run: python git_sync.py --message "GHA race day results"
```

### §3.4 · `capy_trainer_fix.yml`(舊 Capy workflow,REPLACE with this)

```yaml
name: Capy Trainer Refresh (D1 hotfix)

# Replaces the broken httpx/SSR-parsing version. Now reuses Replit's
# selenium TrainerData_Scraper.py which handles SPA correctly.

on:
  schedule:
    - cron: '0 17 * * *'   # HK 01:00 daily
  workflow_dispatch:

permissions:
  contents: write

jobs:
  scrape-trainers:
    runs-on: ubuntu-latest
    timeout-minutes: 30
    env:
      CHROMIUM_PATH: /usr/bin/chromium-browser
      CHROMEDRIVER_PATH: /usr/bin/chromedriver
      GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }

      - uses: actions/setup-python@v5
        with: { python-version: '3.12' }

      - name: Install system Chromium
        run: |
          sudo apt-get update -qq
          sudo apt-get install -y chromium-browser chromium-chromedriver

      - name: Install Python deps
        run: pip install -r requirements.txt

      - name: Run TrainerData only
        run: python TrainerData_Scraper.py

      - name: Commit + push data
        run: python git_sync.py --message "GHA trainer refresh"
```

---

## §4 · `capy_entries.yml` 個案

Capy 之前 4 個 workflow 入面有 `capy_entries.yml`。**唔需要單獨**,因為 EntryList 已經喺 Pool B 入面每日跑。建議:

**方案 X(推薦)**:刪除 `capy_entries.yml`,Pool B daily 已 cover。
**方案 Y**:如果 race day 前要 entry list 即時更新,加埋 race-day morning trigger:
```yaml
on:
  schedule:
    - cron: '0 1 * * 3'   # HK Wed 09:00
    - cron: '0 1 * * 0'   # HK Sun 09:00
```
入面只 run `python EntryList_Scraper.py`。

---

## §5 · Replit-side 必須改嘅 1 個檔(我可以即刻做)

`scraper_utils.py` env-override patch(畀方案 A):

```diff
- CHROMIUM_PATH = "/nix/store/qa9cnw4v5xkxyip6mb9kxqfq1z4x2dx1-chromium-138.0.7204.100/bin/chromium"
- CHROMEDRIVER_PATH = "/nix/store/8zj50jw4w0hby47167kqqsaqw4mm5bkd-chromedriver-unwrapped-138.0.7204.100/bin/chromedriver"
+ import os
+ CHROMIUM_PATH = os.environ.get(
+     "CHROMIUM_PATH",
+     "/nix/store/qa9cnw4v5xkxyip6mb9kxqfq1z4x2dx1-chromium-138.0.7204.100/bin/chromium",
+ )
+ CHROMEDRIVER_PATH = os.environ.get(
+     "CHROMEDRIVER_PATH",
+     "/nix/store/8zj50jw4w0hby47167kqqsaqw4mm5bkd-chromedriver-unwrapped-138.0.7204.100/bin/chromedriver",
+ )
```

Replit 行為 100% 不變(env 未 set → fall back 去 nix path)。

---

## §6 · Cutover sequence(覆蓋 Z plan)

| Step | Action | Owner | Trigger |
|---|---|---|---|
| 1 | Replit 改 `scraper_utils.py` env override | Replit agent | Now |
| 2 | Replit push HANDOVER.md + TrainerData dedup hotfix(pending)| Replit agent | Now |
| 3 | Capy commit 4 個新 GHA YAML 入 `main` | Capy | After Step 1-2 |
| 4 | Capy `workflow_dispatch` Pool B(20 min smoke test)| Capy | After Step 3 |
| 5 | Capy parity test:GHA Pool B output vs Replit Pool B output diff | Capy | After Step 4 |
| 6 | Capy `workflow_dispatch` Pool A delta + RacingData smoke test | Capy | After Step 5 |
| 7 | Replit Reserved VM **降頻**(Pool A/B `sleep 600` between iterations) | Replit user | After Step 6 |
| 8 | Capy 跑足 7 日 daily,parity 持續 OK | Capy | Day 7 |
| 9 | Replit Reserved VM **stop**,tag `capy-handover-baseline-v1` | Replit user | Day 8 |
| 10| Capy 開始 ELO pipeline post-processor | Capy | Day 9+ |

⚠️ **Step 7 critical**:GHA 同 Replit 同時跑 = 4 chrome session,會撞 HKJC rate limit。Replit 必須先降頻先,Capy 先升頻。

---

## §7 · Capy 應該 archive(唔 delete)嘅嘢

```
scrapers_v2/parsers/         → DEPRECATED · wrong abstraction (httpx + SPA HTML parse)
scrapers_v2/orchestrator/    → DEPRECATED · superseded by RunAll_Scrapers.py + GHA cron
.github/workflows/capy_entries.yml      → DEPRECATED (covered by Pool B daily)
.github/workflows/capy_pool_a.yml       → REPLACE with §3.2
.github/workflows/capy_race_daily.yml   → REPLACE with §3.3
.github/workflows/capy_trainer_fix.yml  → REPLACE with §3.4
```

可以開 `archive/2026-04-pre-pivot/` folder 收埋,留作 reference。

---

## §8 · Sanity check Capy 應該做

1. ✅ 上面 4 個 YAML syntax check:`yamllint .github/workflows/capy_*.yml`
2. ✅ Confirm `secrets.GITHUB_TOKEN` 有 `contents: write` perm(workflow `permissions:` block 已包含)
3. ✅ First `workflow_dispatch` Pool B 後讀 log,confirm chromium 啟動 + 至少 1 個 trainer profile fetch 成功
4. ✅ Parity test:GHA push 嘅 `trainers/trainer_profiles.csv` md5 vs Replit push 嘅同檔(同一日)應該幾乎一樣(允許 ±2 行 timing diff)

---

**End of pivot pack.** Capy 有問題喺 issue tracker / 同個 chat 問返 Replit。
