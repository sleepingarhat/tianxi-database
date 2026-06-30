#!/usr/bin/env python3
"""Daily HKJC SpeedPro 速勢圖 scraper (STORE-ONLY, NOT fed into the engine).

Fetches the CURRENT meeting's SpeedPro energy grid (sg_race_N) + form guide
(fg_race_N) from HKJC, strips the embedded base64 pace-map PNGs (huge, not
training-useful as raw pixels), merges per race, and writes one image-free JSON
per race day to speedpro/data/<YYYY-MM-DD>_<VENUE>.json.

Why this exists: accumulate HKJC's own pre-race "速勢圖" prediction signal
(speedproenergy vs energyrequired) so we can later compare 引擎預測 vs SpeedPro
預測 vs 實際賽果, and optionally train on it. HKJC publishes ONLY the current
meeting (no historical backfill), so this must run on/around race days going
forward. The sg_index.expiredate is a natural guard: once a meeting expires we
stop re-committing its (now stale) data. HK only (Sha Tin / Happy Valley).
"""
import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timezone, timedelta

BASE = "https://consvc.hkjc.com/-/media/Sites/JCRW/SpeedPro/current"
REFERER = "https://racing.hkjc.com/zh-hk/local/info/speedpro/speedguide?raceno=1"
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
HKT = timezone(timedelta(hours=8))
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
VENUE_MAP = {"Sha Tin": "ST", "Happy Valley": "HV", "沙田": "ST", "跑馬地": "HV"}


def fetch_json(name, tries=4):
    url = "{}/{}".format(BASE, name)
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": UA,
                "Referer": REFERER,
                "Accept": "application/json,text/plain,*/*",
            })
            with urllib.request.urlopen(req, timeout=60) as r:
                raw = r.read().decode("utf-8-sig")
            return json.loads(raw)
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(2 * (i + 1))
    raise RuntimeError("fetch failed {}: {}".format(name, last))


def strip_images(o):
    if isinstance(o, dict):
        return {k: strip_images(v) for k, v in o.items()
                if not (isinstance(v, str) and v.startswith("data:image"))}
    if isinstance(o, list):
        return [strip_images(x) for x in o]
    return o


def parse_racedate(s):
    # "01/07/2026 9:20 PM" -> "2026-07-01"
    d = s.strip().split()[0]
    dd, mm, yyyy = d.split("/")
    return "{}-{}-{}".format(yyyy, mm.zfill(2), dd.zfill(2))


def parse_expire_hkt(s):
    # "2026-07-02 01:20:00" interpreted as HKT
    return datetime.strptime(s.strip(), "%Y-%m-%d %H:%M:%S").replace(tzinfo=HKT)


def main():
    idx = fetch_json("sg_index")
    racedate_raw = (idx.get("racedate") or "").strip()
    expire_raw = (idx.get("expiredate") or "").strip()
    races = idx.get("zh-hk") or idx.get("en-us") or []
    if not racedate_raw or not races:
        print("::notice::sg_index has no racedate/races - nothing to scrape.")
        return 0

    # Expiry guard: do not re-commit a meeting that has already finished/expired.
    if expire_raw:
        try:
            if datetime.now(HKT) >= parse_expire_hkt(expire_raw):
                print("::notice::SpeedPro meeting expired ({} HKT) - "
                      "no live upcoming meeting; skip.".format(expire_raw))
                return 0
        except Exception as e:  # noqa: BLE001
            print("::warning::cannot parse expiredate {!r}: {}".format(expire_raw, e))

    date_iso = parse_racedate(racedate_raw)
    out = {
        "racedate": date_iso,
        "racedate_raw": racedate_raw,
        "venue": None,
        "source": "hkjc-speedpro",
        "source_base": BASE,
        "scraped_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "lastupdatetime": idx.get("lastupdatetime"),
        "expiredate": expire_raw,
        "races": [],
    }

    venue = None
    for r in races:
        rno = str(r.get("race"))
        rfile = r.get("racefile") or "sg_race_{}.json".format(rno)
        fgfile = rfile.replace("sg_race_", "fg_race_")
        sg = fetch_json(rfile)
        sgblk = sg.get("zh-hk") or sg.get("en-us") or {}
        info_eng = sgblk.get("RaceInfoEng", {})

        if venue is None:
            venue = VENUE_MAP.get(info_eng.get("Racecourse", ""))
            if venue not in ("ST", "HV"):
                print("::notice::venue {!r} not HK (ST/HV) - overseas not "
                      "stored; skip.".format(info_eng.get("Racecourse")))
                return 0
            out["venue"] = venue

        # fg is part of the archive contract. SpeedPro is current-meeting-only
        # (no backfill), so a persistent fg failure must RAISE (after
        # fetch_json's own retries) and turn the workflow red rather than
        # silently committing an incomplete, un-recoverable day.
        fg = fetch_json(fgfile)

        out["races"].append({
            "raceno": int(rno),
            "raceinfo_eng": info_eng,
            "raceinfo_chi": sgblk.get("RaceInfoChi", {}),
            "energy": strip_images(sgblk.get("SpeedPRO", [])),
            "formguide": strip_images(fg.get("SpeedPRO", [])),
        })
        time.sleep(1)  # be gentle on HKJC

    # Completeness gate: SpeedPro is current-meeting-only (no backfill), so never
    # commit a partial day. Fail loudly (workflow red) and let the next
    # cron/dispatch retry rather than archiving holes we can never recover.
    if len(out["races"]) != len(races):
        raise RuntimeError("race count mismatch: got {} expected {}".format(
            len(out["races"]), len(races)))
    for rc in out["races"]:
        if not rc["energy"]:
            raise RuntimeError("race {} has empty energy grid".format(rc["raceno"]))
        if not rc["formguide"]:
            raise RuntimeError("race {} has empty formguide".format(rc["raceno"]))

    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, "{}_{}.json".format(date_iso, venue))

    # Dedupe: if the existing file is identical apart from scraped_at, leave it
    # untouched so we don't create no-op daily commits.
    if os.path.exists(path):
        try:
            old = json.load(open(path, encoding="utf-8"))
            a = dict(old)
            a.pop("scraped_at", None)
            b = dict(out)
            b.pop("scraped_at", None)
            if a == b:
                print("::notice::{} unchanged - skip rewrite.".format(os.path.basename(path)))
                return 0
        except Exception as e:  # noqa: BLE001
            print("::warning::could not compare existing {}: {}".format(path, e))

    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    print("::notice::wrote {} ({:.0f} KB, {} races, venue {})".format(
        path, os.path.getsize(path) / 1024, len(out["races"]), venue))
    return 0


if __name__ == "__main__":
    sys.exit(main())
