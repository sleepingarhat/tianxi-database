#!/usr/bin/env python3
"""TX-ORACLE racebill posters — certificate style + meeting grid."""
from __future__ import annotations

import json, os, urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1440
INK = (58, 38, 20)
MUTE = (118, 94, 60)
PAPER = (252, 246, 232)
GOLD = (176, 138, 48)
GOLD_DEEP = (130, 98, 32)
LINE = (186, 152, 82)
GREEN = (14, 108, 56)

def _font_pick(*cands):
    for c in cands:
        if Path(c).exists():
            return c
    return cands[0]

SERIF_B = _font_pick(
    "/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc",
    "/usr/share/fonts/opentype/noto/NotoSerifCJKtc-Bold.otf",
)
SERIF_R = _font_pick(
    "/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSerifCJKtc-Regular.otf",
    SERIF_B,
)
SANS_R = _font_pick(
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJKtc-Regular.otf",
    SERIF_R,
)
SANS_B = _font_pick(
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJKtc-Bold.otf",
    SERIF_B,
)
HK = 4
OUT = Path(os.environ.get("TX_POSTER_OUT", "/tmp/tx-posters"))
WREATH = Path(__file__).resolve().parent / "assets" / "wreath_badge.png"
M = 44


def F(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size, index=HK)


def frame(im: Image.Image, d: ImageDraw.ImageDraw, w: int, h: int) -> None:
    d.rectangle([M, M, w - M, h - M], outline=GOLD_DEEP, width=4)
    d.rectangle([M + 10, M + 10, w - M - 10, h - M - 10], outline=LINE, width=1)
    L = 28
    for x, y, dx, dy in (
        (M, M, 1, 1),
        (w - M, M, -1, 1),
        (M, h - M, 1, -1),
        (w - M, h - M, -1, -1),
    ):
        d.line([(x, y + dy * L), (x, y), (x + dx * L, y)], fill=GOLD_DEEP, width=4)


def ornament(d: ImageDraw.ImageDraw, y: int, w: int = W) -> None:
    mid = w / 2
    d.line([(120, y), (mid - 36, y)], fill=LINE, width=2)
    d.line([(mid + 36, y), (w - 120, y)], fill=LINE, width=2)
    d.ellipse([mid - 8, y - 8, mid + 8, y + 8], outline=GOLD_DEEP, width=2)
    d.ellipse([mid - 3, y - 3, mid + 3, y + 3], fill=GOLD)


def flourish(d: ImageDraw.ImageDraw, y: int, w: int = W) -> None:
    mid = w / 2
    d.line([(120, y), (mid - 48, y)], fill=LINE, width=2)
    d.line([(mid + 48, y), (w - 120, y)], fill=LINE, width=2)
    d.polygon([(mid, y - 10), (mid + 10, y), (mid, y + 10), (mid - 10, y)], outline=GOLD_DEEP)
    d.ellipse([mid - 3, y - 3, mid + 3, y + 3], fill=GOLD)


def paste_wreath(im: Image.Image, d: ImageDraw.ImageDraw, cx: int, cy: int) -> None:
    if WREATH.exists():
        badge = Image.open(WREATH).convert("RGBA")
        badge = badge.resize((156, 174), Image.Resampling.LANCZOS)
        x, y = cx - badge.size[0] // 2, cy - badge.size[1] // 2 - 6
        im.paste(badge, (x, y), badge)
    else:
        r = 52
        d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=GOLD, width=3)
    d.text((cx, cy + 8), "1", font=F(SERIF_B, 40), fill=GOLD, anchor="mm")


def rank_mark(im: Image.Image, d: ImageDraw.ImageDraw, cx: int, cy: int, n: int) -> None:
    if n == 1:
        paste_wreath(im, d, cx, cy)
    elif n == 4:
        fnt = F(SERIF_B, 50)
        for dx, dy in ((-2,0),(2,0),(0,-2),(0,2),(-1,-1),(1,-1),(-1,1),(1,1)):
            d.text((cx+dx, cy+dy), "4", font=fnt, fill=GOLD, anchor="mm")
        d.text((cx, cy), "4", font=fnt, fill=PAPER, anchor="mm")
    else:
        r = 44
        d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=GOLD, width=3)
        d.text((cx, cy + 2), str(n), font=F(SERIF_B, 38), fill=INK, anchor="mm")


def render_pre(race: dict, dest: str = "tx_poster_pre"):
    im = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(im)
    frame(im, d, W, H)
    d.text((W / 2, 78), "TX-ORACLE天喜引擎 · 賽前預測", font=F(SERIF_B, 40), fill=INK, anchor="mt")
    ornament(d, 136)
    d.text((W / 2, 154), race.get("date_line", ""), font=F(SERIF_B, 48), fill=INK, anchor="mt")
    flourish(d, 228)
    d.text((W / 2, 248), race.get("meta", ""), font=F(SERIF_R, 28), fill=MUTE, anchor="mt")

    picks = race.get("picks") or []
    y = 310
    row_h = 198
    for i, p in enumerate(picks[:4], 1):
        rank_mark(im, d, 168, y + 52, i)
        no = str(p.get("no", ""))
        name = p.get("name", "")
        d.text((270, y + 10), no, font=F(SERIF_B, 46), fill=INK)
        d.text((360, y + 14), name, font=F(SERIF_B, 44), fill=INK)
        if i == 1:
            tw = d.textlength(name, font=F(SERIF_B, 40))
            d.text((360 + tw + 16, y + 26), "★", font=F(SERIF_B, 30), fill=GOLD)
        d.text((360, y + 72), p.get("sub", ""), font=F(SANS_R, 22), fill=MUTE)
        x = 270
        while x < 980:
            d.ellipse([x, y + 128, x + 3, y + 131], fill=LINE)
            x += 10
        y += row_h

    chips = [str(p.get("no", "")) for p in picks[:4]]
    cw, ch, gap = 168, 92, 20
    total = len(chips) * cw + max(0, len(chips) - 1) * gap
    x = (W - total) / 2
    cy = y - 36
    if cy + ch > H - M - 24:
        cy = H - M - 24 - ch
    for n in chips:
        d.rounded_rectangle([x, cy, x + cw, cy + ch], radius=18, outline=GOLD_DEEP, width=3)
        d.text((x + cw / 2, cy + ch / 2), n, font=F(SERIF_B, 46), fill=INK, anchor="mm")
        x += cw + gap

    OUT.mkdir(parents=True, exist_ok=True)
    png, pdf = OUT / f"{dest}.png", OUT / f"{dest}.pdf"
    im.save(png)
    im.convert("RGB").save(pdf, "PDF", resolution=150)
    return png, pdf


def render_post(race: dict, dest: str = "tx_poster_post"):
    im = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(im)
    frame(im, d, W, H)
    d.text((W / 2, 78), "TX-ORACLE天喜引擎 · 預測與賽果比對", font=F(SERIF_B, 32), fill=INK, anchor="mt")
    ornament(d, 136)
    d.text((W / 2, 154), race.get("date_line", ""), font=F(SERIF_B, 48), fill=INK, anchor="mt")
    flourish(d, 228)

    pred = [str(x) for x in (race.get("pred") or [])][:4]
    actual = [str(x) for x in (race.get("actual") or [])][:4]
    hit = set(pred) & set(actual)
    lx, rx = 340, 740
    d.text((lx, 262), "模型首四", font=F(SANS_R, 22), fill=MUTE, anchor="mt")
    d.text((rx, 262), "賽果頭四", font=F(SANS_R, 22), fill=MUTE, anchor="mt")
    d.text((W / 2, 262), f"命中 {len(hit)}/4", font=F(SERIF_B, 26), fill=GOLD, anchor="mt")
    d.line([(540, 310), (540, 1188)], fill=LINE, width=1)
    yy = 310
    for i in range(4):
        a = pred[i] if i < len(pred) else "—"
        b = actual[i] if i < len(actual) else "—"
        d.text((lx, yy), a, font=F(SERIF_B, 92), fill=GOLD if a in hit else INK, anchor="mt")
        d.text((rx, yy), b, font=F(SERIF_B, 92), fill=GOLD if b in hit else INK, anchor="mt")
        yy += 220

    rows = race.get("payouts") or []
    box_bot = H - M - 26
    box_top = box_bot - 132
    d.rectangle([M + 26, box_top, W - M - 26, box_bot], outline=GOLD_DEEP, width=2)
    d.line([(360, box_top + 16), (360, box_bot - 16)], fill=LINE, width=1)
    d.line([(720, box_top + 16), (720, box_bot - 16)], fill=LINE, width=1)
    mid = (box_top + box_bot) / 2
    if rows:
        row = rows[0]
        d.text((210, mid), f"命中{row['pool']}", font=F(SERIF_B, 28), fill=GOLD, anchor="mm")
        d.text((540, mid), "$10一注", font=F(SANS_R, 24), fill=MUTE, anchor="mm")
        d.text((860, mid), f"派彩{row['payout']}", font=F(SERIF_B, 30), fill=GREEN, anchor="mm")

    OUT.mkdir(parents=True, exist_ok=True)
    png, pdf = OUT / f"{dest}.png", OUT / f"{dest}.pdf"
    im.save(png)
    im.convert("RGB").save(pdf, "PDF", resolution=150)
    return png, pdf


def render_meeting(meet: dict, dest: str = "tx_poster_day"):
    w, h = 1600, 1100
    im = Image.new("RGB", (w, h), PAPER)
    d = ImageDraw.Draw(im)
    frame(im, d, w, h)
    d.text((w / 2, 70), "TX-ORACLE天喜引擎 · 全日預測與賽果比對", font=F(SERIF_B, 34), fill=INK, anchor="mt")
    ornament(d, 124, w)
    d.text((w / 2, 144), meet.get("date_line", ""), font=F(SERIF_B, 36), fill=INK, anchor="mt")
    flourish(d, 204, w)

    headers = ["場次", "第一名", "第二名", "第三名", "第四名"]
    races = meet.get("races") or []
    left, top = 80, 240
    right, bot = w - 80, h - 80
    cols = 5
    rows_n = 1 + max(len(races), 1)
    cw = (right - left) / cols
    rh = (bot - top) / rows_n

    d.rectangle([left, top, right, top + rh], fill=(138, 106, 36))
    for i, hd in enumerate(headers):
        d.text((left + cw * i + cw / 2, top + rh / 2), hd, font=F(SERIF_B, 22), fill=PAPER, anchor="mm")

    for r_i, race in enumerate(races):
        y0 = top + rh * (r_i + 1)
        y1 = y0 + rh
        d.line([(left, y0), (right, y0)], fill=LINE, width=1)
        d.text((left + cw / 2, (y0 + y1) / 2), str(race.get("n", "")), font=F(SERIF_B, 24), fill=INK, anchor="mm")
        picks = race.get("picks") or []
        hits = set(str(x) for x in (race.get("hits") or []))
        for c, p in enumerate(picks[:4]):
            x = left + cw * (c + 1)
            no = str(p.get("no", ""))
            name = p.get("name", "")
            is_hit = no in hits
            if is_hit:
                d.rectangle([x + 4, y0 + 6, x + cw - 4, y1 - 6], fill=(245, 230, 190))
            color = GOLD_DEEP if is_hit else INK
            label = f"{no} {name}"
            d.text((x + cw / 2, (y0 + y1) / 2), label, font=F(SERIF_B if is_hit else SERIF_R, 20), fill=color, anchor="mm")
            if is_hit:
                d.text((x + cw - 16, y0 + 16), "★", font=F(SERIF_B, 14), fill=GOLD, anchor="mm")

    for i in range(cols + 1):
        x = left + cw * i
        d.line([(x, top), (x, bot)], fill=LINE, width=1)
    d.rectangle([left, top, right, bot], outline=GOLD_DEEP, width=2)

    OUT.mkdir(parents=True, exist_ok=True)
    png, pdf = OUT / f"{dest}.png", OUT / f"{dest}.pdf"
    im.save(png)
    im.convert("RGB").save(pdf, "PDF", resolution=150)
    return png, pdf


def tg_send_document(pdf_path: Path, caption: str = "") -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    channel = os.environ.get("TG_CHANNEL", "@TX_Oracle")
    if os.environ.get("TX_DRY_RUN"):
        print("dry-run", pdf_path, caption)
        return
    if not token:
        raise SystemExit("missing TELEGRAM_BOT_TOKEN")
    boundary = "txposter"
    with open(pdf_path, "rb") as f:
        body_file = f.read()
    chunks = []
    def field(name, value):
        chunks.append(("\r\n--%s\r\nContent-Disposition: form-data; name=\"%s\"\r\n\r\n" % (boundary, name)).encode())
        chunks.append(value if isinstance(value, bytes) else str(value).encode())
    field("chat_id", channel)
    field("caption", caption)
    chunks.append(("\r\n--%s\r\nContent-Disposition: form-data; name=\"document\"; filename=\"%s\"\r\nContent-Type: application/pdf\r\n\r\n" % (boundary, pdf_path.name)).encode())
    chunks.append(body_file)
    chunks.append(("\r\n--%s--\r\n" % boundary).encode())
    req = urllib.request.Request(
        "https://api.telegram.org/bot%s/sendDocument" % token,
        data=b"".join(chunks),
        headers={"Content-Type": "multipart/form-data; boundary=%s" % boundary},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        resp = json.loads(r.read().decode())
    if not resp.get("ok"):
        raise SystemExit(resp)
    print("posted", resp.get("result", {}).get("message_id"), pdf_path.name)
