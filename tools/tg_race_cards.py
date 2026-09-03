#!/usr/bin/env python3
"""Per-race Telegram cards for @TX_Oracle."""
from __future__ import annotations
import argparse, html, json, os, sys, time, urllib.error, urllib.request
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
        print(text); return
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        sys.exit(2)
    url = "https://api.telegram.org/bot%s/sendMessage" % token
    payload = json.dumps({"chat_id": CHANNEL, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=40) as r:
        resp = json.loads(r.read().decode("utf-8"))
    if not resp.get("ok"):
        sys.exit(3)
    print("posted ok", resp.get("result", {}).get("message_id"))

def venue_name(venue, fallback=None):
    return VENUE_CH.get(venue, fallback or venue or "")

def pick_nums(items, key="horseNumber"):
    out = []
    for p in items or []:
        v = p.get(key) if isinstance(p, dict) else p
        if v not in (None, ""):
            out.append(str(v))
    return out

def horse_meta(p):
    bits = []
    if p.get("jockeyCh") or p.get("jockey"): bits.append(p.get("jockeyCh") or p.get("jockey"))
    if p.get("trainerCh") or p.get("trainer"): bits.append(p.get("trainerCh") or p.get("trainer"))
    if p.get("draw") not in (None, ""): bits.append("檔%s" % p.get("draw"))
    wt = p.get("actualWeight") or p.get("declaredWeight") or p.get("weight")
    if wt not in (None, ""): bits.append("%s磅" % str(wt).replace("磅", ""))
    st = p.get("runningStyle") or p.get("styleLabel") or p.get("style") or ""
    if st and str(st)[:1] in "放前中後": bits.append(str(st)[:1])
    return " · ".join(str(x) for x in bits)

def cmd_prerace(args):
    data = api_get("/api/analyze/today-picks")
    date = data.get("date")
    if not date:
        print("no meeting"); return
    if date != hk_today().isoformat() and not args.force:
        print("not today"); return
    races = [r for r in (data.get("races") or []) if r.get("picks")]
    vname = venue_name(data.get("venue"), data.get("venueName"))
    for r in races:
        picks = sorted(r.get("picks") or [], key=lambda p: p.get("rank") or 99)[:4]
        lines = ["<b>TX-ORACLE天喜引擎 · 賽前預測</b>", "%s　%s　第 %s 場" % (fmt_date(date), e(vname), e(r.get("raceNumber")))]
        meta = []
        if r.get("distance"): meta.append("%sm" % r.get("distance"))
        if r.get("class"): meta.append("第%s班" % r.get("class"))
        if meta: lines.append(" · ".join(str(x) for x in meta))
        lines.append("")
        for i, p in enumerate(picks, 1):
            name = p.get("nameCh") or p.get("nameEn") or "?"
            line = "%d. %s號 %s" % (i, e(p.get("horseNumber")), e(name))
            extra = horse_meta(p)
            if extra: line += "\n    %s" % e(extra)
            lines.append(line)
        lines += ["", '<a href="%s/cards/">網站</a>' % SITE_BASE, "<i>%s</i>" % e(DISCLAIMER)]
        tg_send("\n".join(lines)); time.sleep(1.2)

def latest_settled(today):
    data = api_get("/api/meetings")
    for m in data.get("meetings") or []:
        if m.get("totalRaces") and m.get("date") and m.get("date") <= today:
            return m.get("date"), m.get("venue")
    return None, None

def cmd_postrace(args):
    today = hk_today().isoformat()
    date = args.date or latest_settled(today)[0]
    if not date:
        print("no settled"); return
    try:
        data = api_get("/api/analyze/hit-rate?date=%s" % date)
    except urllib.error.HTTPError as ex:
        if ex.code == 404: return
        raise
    vname = venue_name(data.get("venue"))
    for r in data.get("races") or []:
        pred = pick_nums(r.get("predictedTop4"))
        act4 = pick_nums(r.get("actualTop4"))
        act3 = pick_nums(r.get("actualTop3"))
        both = [x for x in act4 if x in set(pred)]
        trio = len(act3) == 3 and all(x in set(pred) for x in act3)
        first4 = len(act4) == 4 and all(x in set(pred) for x in act4)
        win = bool(pred and act4 and pred[0] == act4[0])
        quin = len(pred[:2]) == 2 and set(pred[:2]) == set(act4[:2])
        qp = len(pred[:2]) == 2 and all(x in set(act3) for x in pred[:2])
        lines = [
            "<b>TX-ORACLE天喜引擎 · 預測與賽果比對</b>",
            "%s　%s　第 %s 場" % (fmt_date(date), e(vname), e(r.get("raceNumber"))),
            "",
            "模型首四　%s" % e(" ".join(pred) or "—"),
            "賽果頭四　%s" % e(" ".join(act4) or "—"),
            "命中　<b>%d/4</b>" % len(both),
        ]
        hits = []
        if win: hits.append("頭馬 命中")
        if qp: hits.append("位置Q 命中")
        if quin: hits.append("連贏 命中")
        if trio: hits.append("單T 命中")
        if first4: hits.append("四連環 命中")
        if hits:
            lines.append("")
            lines.extend(hits)
        lines += ["", '<a href="%s/cards/">網站</a>' % SITE_BASE, "<i>%s</i>" % e(DISCLAIMER)]
        tg_send("\n".join(lines)); time.sleep(1.2)

def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p1 = sub.add_parser("prerace-races"); p1.add_argument("--force", action="store_true"); p1.set_defaults(func=cmd_prerace)
    p2 = sub.add_parser("postrace-races"); p2.add_argument("--date"); p2.set_defaults(func=cmd_postrace)
    args = ap.parse_args(); args.func(args)

if __name__ == "__main__":
    main()
