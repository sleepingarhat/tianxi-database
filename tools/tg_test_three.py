#!/usr/bin/env python3
"""Send exactly 3 locked posters for one settled meeting to @TX_Oracle."""
from __future__ import annotations

import json
import os
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tx_poster import render_meeting, render_post, render_pre, tg_send_document

API = os.environ.get("TX_API_BASE", "https://www.tianxi.racing").rstrip("/")
VENUE = {"ST": "沙田", "HV": "跑馬地"}


def api(path):
    req = urllib.request.Request(API + path, headers={"User-Agent": "tx-tg-test", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=40) as r:
        return json.loads(r.read().decode())


def main():
    date = sys.argv[1] if len(sys.argv) > 1 else "2026-07-12"
    data = api("/api/analyze/hit-rate?date=%s" % date)
    vname = VENUE.get(data.get("venue"), data.get("venue") or "")
    _y, m, d = date.split("-")
    date_line = "%s月%s日　%s" % (int(m), int(d), vname)
    races = data.get("races") or []
    if not races:
        raise SystemExit("no races")

    r1 = races[0]
    picks = [{"no": p.get("horseNumber"), "name": p.get("nameCh") or "", "sub": ""} for p in (r1.get("predictedTop4") or [])[:4]]
    meta = []
    if r1.get("distance"):
        meta.append("%s米" % r1.get("distance"))
    if r1.get("going"):
        meta.append(r1.get("going"))
    _png, pre_pdf = render_pre(
        {"date_line": "%s　第 %s 場" % (date_line, r1.get("raceNumber")), "meta": " · ".join(meta), "picks": picks},
        dest="TX-%s-R%s-pre" % (date, r1.get("raceNumber")),
    )
    tg_send_document(pre_pdf, "TX-ORACLE · %s 第%s場 賽前預測" % (date, r1.get("raceNumber")))

    post_src = None
    for r in races:
        if r.get("qpHit") or r.get("top1Hit"):
            post_src = r
            break
    post_src = post_src or races[min(2, len(races) - 1)]
    pred = [str(p.get("horseNumber")) for p in (post_src.get("predictedTop4") or [])][:4]
    act = [str(p.get("horseNumber")) for p in (post_src.get("actualTop4") or [])][:4]
    pays = []
    if post_src.get("qpHit"):
        pays.append({"pool": "位置Q", "payout": "—"})
    elif post_src.get("top1Hit"):
        pays.append({"pool": "獨贏", "payout": "—"})
    _png, post_pdf = render_post(
        {"date_line": "%s　第 %s 場" % (date_line, post_src.get("raceNumber")), "pred": pred, "actual": act, "payouts": pays},
        dest="TX-%s-R%s-post" % (date, post_src.get("raceNumber")),
    )
    tg_send_document(post_pdf, "TX-ORACLE · %s 第%s場 預測與賽果比對" % (date, post_src.get("raceNumber")))

    day_races = []
    for r in races:
        picks, hits = [], []
        for p in (r.get("predictedTop4") or [])[:4]:
            no = str(p.get("horseNumber"))
            picks.append({"no": no, "name": p.get("nameCh") or ""})
            if p.get("hit"):
                hits.append(no)
        day_races.append({"n": r.get("raceNumber"), "picks": picks, "hits": hits})
    _png, day_pdf = render_meeting({"date_line": date_line, "races": day_races}, dest="TX-%s-day" % date)
    tg_send_document(day_pdf, "TX-ORACLE · %s 全日預測與賽果比對" % date)
    print("sent 3 cards", date)


if __name__ == "__main__":
    main()
