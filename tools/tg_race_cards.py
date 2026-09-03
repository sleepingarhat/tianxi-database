#!/usr/bin/env python3
"""Per-race Telegram cards for @TX_Oracle.

Subcommands:
  prerace-races   One pre-race prediction card per race.
  postrace-races  One post-race comparison card per settled race.

Env: TELEGRAM_BOT_TOKEN, TG_CHANNEL=@TX_Oracle, TX_API_BASE, TX_SITE_BASE, TX_DRY_RUN
"""
from __future__ import annotations

import argparse
import html
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

HK_TZ = timezone(timedelta(hours=8))
API_BASE = os.environ.get("TX_API_BASE", "https://tianxi.racing").rstrip("/")
SITE_BASE = os.environ.get("TX_SITE_BASE", "https://www.tianxi.racing").rstrip("/")
CHANNEL = os.environ.get("TG_CHANNEL", "@TX_Oracle")
WEEKDAY_CH = ["週一", "週二", "週三", "週四", "週五", "週六", "週日"]
VENUE_CH = {"ST": "沙田", "HV": "跑馬地"}
DISCLAIMER = "免責：數據分析展示，非投注建議。只供 18 歲或以上人士。"


def e(s):
    return html.escape(str(s if s is not None else ""))


def hk_today():
    return datetime.now(HK_TZ).date()


def fmt_date(iso):
    try:
        d = datetime.strptime(iso, "%Y-%m-%d").date()
        return "%d月%d日（%s）" % (d.month, d.day, WEEKDAY_CH[d.weekday()])
    except Exception:
        return iso


def api_get(path):
    req = urllib.request.Request(API_BASE + path, headers={"User-Agent": "tx-tg-cards", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=40) as r:
        return json.loads(r.read().decode("utf-8"))


def tg_send(text):
    if os.environ.get("TX_DRY_RUN"):
        print("----- DRY RUN -----")
        print(text)
        print("----- END -----")
        return
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        print("ERROR: TELEGRAM_BOT_TOKEN not set", file=sys.stderr)
        sys.exit(2)
    url = "https://api.telegram.org/bot%s/sendMessage" % token
    payload = json.dumps({"chat_id": CHANNEL, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            resp = json.loads(r.read().decode("utf-8"))
        if not resp.get("ok"):
            print("ERROR: telegram not-ok: %s" % json.dumps(resp), file=sys.stderr)
            sys.exit(3)
        print("posted ok, message_id=%s" % resp.get("result", {}).get("message_id"))
    except urllib.error.HTTPError as ex:
        print("ERROR: telegram HTTP %s: %s" % (ex.code, ex.read().decode("utf-8", "replace")), file=sys.stderr)
        sys.exit(3)


def venue_name(venue, fallback=None):
    return VENUE_CH.get(venue, fallback or venue or "")


def pick_nums(items, key="horseNumber"):
    out = []
    for p in items or []:
        v = p.get(key) if isinstance(p, dict) else p
        if v not in (None, ""):
            out.append(str(v))
    return out


def fmt_pct(v):
    try:
        n = float(v)
    except (TypeError, ValueError):
        return "—"
    if n <= 1:
        n *= 100
    return "%g%%" % (round(n * 10) / 10)


def cmd_prerace(args):
    data = api_get("/api/analyze/today-picks")
    date = data.get("date")
    if not date:
        print("no upcoming meeting; skip")
        return
    today = hk_today().isoformat()
    if date != today and not args.force:
        print("upcoming meeting %s is not today (%s); skip" % (date, today))
        return
    races = [r for r in (data.get("races") or []) if r.get("picks")]
    if not races:
        print("no races with picks; skip")
        return
    vname = venue_name(data.get("venue"), data.get("venueName"))
    card_url = SITE_BASE + "/cards/"
    for r in races:
        picks = sorted(r.get("picks") or [], key=lambda p: p.get("rank") or 99)[:4]
        lines = ["<b>【天喜 · 賽前預測卡】</b>", "%s　%s　第 %s 場" % (fmt_date(date), e(vname), e(r.get("raceNumber")))]
        meta = []
        if r.get("distance"):
            meta.append("%sm" % r.get("distance"))
        if r.get("class"):
            meta.append("第%s班" % r.get("class"))
        if meta:
            lines.append(" · ".join(str(x) for x in meta))
        lines += ["", "<b>模型首四</b>（場內相對排序）"]
        for i, p in enumerate(picks, 1):
            name = p.get("nameCh") or p.get("nameEn") or "?"
            no = p.get("horseNumber")
            extra = []
            if p.get("jockeyCh"):
                extra.append(p.get("jockeyCh"))
            if p.get("draw") is not None:
                extra.append("檔%s" % p.get("draw"))
            tail = ("　" + " · ".join(str(x) for x in extra)) if extra else ""
            lines.append("%d. %s號 %s　%s%s" % (i, e(no), e(name), e(fmt_pct(p.get("pWin"))), e(tail)))
        box = "　".join(str(p.get("horseNumber")) for p in picks if p.get("horseNumber") is not None)
        lines += ["", "單T箱（頭三毋須順序）：<b>%s</b>" % e(box), "四連環箱（頭四毋須順序）：<b>%s</b>" % e(box), "三重彩要順序，本卡唔當三重彩注項。", "", '<a href="%s">網站逐場卡</a>' % card_url, "<i>%s</i>" % e(DISCLAIMER)]
        tg_send("\n".join(lines))
        time.sleep(1.2)
    print("posted %d pre-race cards" % len(races))


def latest_settled(today):
    data = api_get("/api/meetings")
    for m in data.get("meetings") or []:
        if m.get("totalRaces") and m.get("date") and m.get("date") <= today:
            return m.get("date"), m.get("venue")
    return None, None


def cmd_postrace(args):
    today = hk_today().isoformat()
    date = args.date
    if not date:
        date, _ = latest_settled(today)
    if not date:
        print("no settled meeting; skip")
        return
    try:
        data = api_get("/api/analyze/hit-rate?date=%s" % date)
    except urllib.error.HTTPError as ex:
        if ex.code == 404:
            print("hit-rate not ready for %s; skip" % date)
            return
        raise
    races = data.get("races") or []
    if not races:
        print("no races; skip")
        return
    vname = venue_name(data.get("venue"))
    card_url = SITE_BASE + "/cards/"
    for r in races:
        pred = pick_nums(r.get("predictedTop4"))
        act4 = pick_nums(r.get("actualTop4"))
        act3 = pick_nums(r.get("actualTop3"))
        pset = set(pred)
        ov = len([x for x in act4 if x in pset])
        trio = len(act3) == 3 and all(x in pset for x in act3)
        first4 = len(act4) == 4 and all(x in pset for x in act4)
        win = bool(pred and act4 and pred[0] == act4[0])
        pred2, act2 = pred[:2], act4[:2]
        quin = len(pred2) == 2 and set(pred2) == set(act2)
        qp = len(pred2) == 2 and all(x in set(act3) for x in pred2)
        def mark(ok):
            return "中" if ok else "唔中"
        lines = [
            "<b>【天喜 · 對賬卡】</b>",
            "%s　%s　第 %s 場" % (fmt_date(date), e(vname), e(r.get("raceNumber"))),
            "",
            "模型首四　<b>%s</b>" % e("　".join(pred) or "—"),
            "實際頭四　<b>%s</b>" % e("　".join(act4) or "—"),
            "頭四重疊　<b>%d/4</b>" % ov,
            "",
            "頭馬　%s" % mark(win),
            "位置Q　%s　（首兩選入頭三）" % mark(qp),
            "連贏　%s　（首兩選即頭兩，毋須順序）" % mark(quin),
            "單T　%s　（首四入三隻頭三，毋須順序）" % mark(trio),
            "四連環　%s　（首四即頭四，毋須順序）" % mark(first4),
            "",
            "單T ≠ 三重彩。三重彩要順序，本卡唔計。",
            '<a href="%s">網站逐場卡</a>' % card_url,
            "<i>%s</i>" % e(DISCLAIMER),
        ]
        tg_send("\n".join(lines))
        time.sleep(1.2)
    print("posted %d post-race cards" % len(races))


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p1 = sub.add_parser("prerace-races")
    p1.add_argument("--force", action="store_true")
    p1.set_defaults(func=cmd_prerace)
    p2 = sub.add_parser("postrace-races")
    p2.add_argument("--date")
    p2.set_defaults(func=cmd_postrace)
    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
