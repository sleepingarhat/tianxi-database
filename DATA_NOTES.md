# HKJC 數據集說明

數據抓取期間：2016-01-01 至 2026-04-15

---

## 📊 數據覆蓋範圍

| 類別 | 日期範圍 | 完整性 |
|---|---|---|
| 賽果 (results) | 2016-01-01 → 2026-04-15 | 完整 |
| 派彩 (dividends) | 2016-01-01 → 2026-04-15 | 完整 |
| 分段時間 (sectional_times) | 2016-01-01 → 2026-04-15 | 完整 |
| 沿途走勢評述 (commentary) | 2016-01-01 → 2026-04-15 | 完整 |
| 賽事影片連結 (video_links) | 2016-01-01 → 2026-04-15 | 完整 |
| 試閘 (trials) | 2025-03-13 → 2026-04-16 | 受 HKJC 限制 |

---

## ⚠️ 取消／改期賽馬日（無 results CSV）

以下日期因惡劣天氣（八號風球／黑色暴雨）取消，HKJC 系統有派彩退款／評述等記錄但無實際賽果：

- 2018-09-16
- 2019-09-18
- 2019-11-13
- 2021-10-13
- 2022-11-02
- 2023-10-08

呢啲日期入面 `dividends_*.csv`、`sectional_times_*.csv`、`commentary_*.csv`、`video_links_*.csv` 仍然存在（包含退款資料）。

---

## ⚠️ 試閘數據限制

HKJC 試閘頁面**只保留最近 176 個試閘日**（約一年），早於 2025-03-13 嘅試閘紀錄已從官方網站移除，無法抓取。

- 已抓取試閘日數：176
- 已抓取試閘場次：705
- 已抓取試閘成績行數：5,457

---

## 🚫 HKJC 已永久移除嘅數據（無法抓取）

以下類別 HKJC 官方網站均回傳 404：

1. 排位表（歷史）
2. 天氣／跑道狀況（歷史） — 部分資訊已包含在 `results` 嘅 `going` / `course` 欄位
3. 速勢能量
4. 馬匹搬遷紀錄
5. 裝備登記冊 — 每場實際配戴裝備已包含在 `commentary` 嘅 `gear` 欄位
6. 傷患紀錄
7. 上仗備忘

---

## 📁 檔案結構

```
data/YYYY/
  results_YYYY-MM-DD.csv
  dividends_YYYY-MM-DD.csv
  sectional_times_YYYY-MM-DD.csv
  commentary_YYYY-MM-DD.csv
  video_links_YYYY-MM-DD.csv

trials/
  trial_sessions.csv      # 一行一個試閘場次
  trial_results.csv       # 一行一匹馬一個試閘

horses/
  profiles/horse_profiles.csv     # 一行一匹馬（檔案＋血統）
  form_records/<horse_no>.csv     # 每匹馬一個檔案（往績）
  trackwork/<date>.csv            # 每日晨操

jockeys/
  jockey_profiles.csv
  records/<jockey>.csv

trainers/
  trainer_profiles.csv
  records/<trainer>.csv
```

---

## 🔁 失敗紀錄檔案

- `failed_dates.log` — 賽果抓取失敗（已重試 2 次）
- `failed_horses.log` — 馬匹資料抓取失敗
- `failed_trials.log` — 試閘抓取失敗
- `failed_trackwork.log` — 晨操抓取失敗
- `failed_jockeys.log` — 騎師資料抓取失敗
- `failed_trainers.log` — 練馬師資料抓取失敗

`failed_dates.log` 內容：2016-01-02、2016-01-03（呢兩日本身無賽馬，並非缺漏）。
