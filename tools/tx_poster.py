#!/usr/bin/env python3
"""TX-ORACLE poster renderer. Follows tianxi-site/DESIGN.md. One race → PNG + PDF."""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1440
INK = (11, 11, 11)
INK_SOFT = (42, 42, 40)
INK_MUTE = (95, 92, 82)
PAPER = (253, 251, 245)
PAPER2 = (245, 241, 228)
TICKER = (11, 22, 18)
TICKER_FG = (240, 235, 221)
TAN = (212, 183, 138)
GOLD = (184, 145, 47)
GOLD2 = (212, 161, 30)
GOLD3 = (245, 215, 122)
GREEN = (0, 132, 61)

SERIF_B = "/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc"
SANS_R = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
SANS_B = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
HK = 4
OUT = Path("/tmp/tx-posters")


def font(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size, index=HK)


def draw_header(d: ImageDraw.ImageDraw, kicker: str) -> None:
    d.rectangle([0, 0, W, 132], fill=TICKER)
    d.rectangle([0, 132, 8, H], fill=GOLD)
    d.text((56, 46), "喜", font=font(SERIF_B, 36), fill=GOLD3)
    d.text((108, 54), kicker, font=font(SANS_B, 28), fill=TAN)


def draw_meeting(d: ImageDraw.ImageDraw, date_line: str, race_line: str, meta: str, hit: str | None = None) -> int:
    d.text((56, 168), date_line, font=font(SANS_R, 26), fill=INK_MUTE)
    d.text((56, 210), race_line, font=font(SERIF_B, 56), fill=INK)
    if hit:
        d.text((1024, 214), hit, font=font(SANS_B, 36), fill=GOLD, anchor="ra")
        d.text((1024, 258), "命中", font=font(SANS_B, 22), fill=GOLD, anchor="ra")
    if meta:
        d.text((56, 284), meta, font=font(SANS_R, 24), fill=INK_MUTE)
        return 330
    return 300


def save(im: Image.Image, stem: str) -> tuple[Path, Path]:
    OUT.mkdir(parents=True, exist_ok=True)
    png = OUT / f"{stem}.png"
    pdf = OUT / f"{stem}.pdf"
    im.save(png, "PNG")
    im.convert("RGB").save(pdf, "PDF", resolution=150)
    return png, pdf


def render_pre(race: dict, dest: str = "tx_poster_pre") -> tuple[Path, Path]:
    im = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(im)
    draw_header(d, "TX-ORACLE天喜引擎 · 賽前預測")
    y0 = draw_meeting(d, race.get("date_line", ""), race.get("race_line", ""), race.get("meta", ""))
    d.line([(56, y0), (1024, y0)], fill=(220, 208, 190), width=2)
    y = y0 + 36
    picks = race.get("picks") or []
    for i, p in enumerate(picks[:4], 1):
        accent = i == 1
        if accent:
            d.rectangle([48, y - 8, 54, y + 108], fill=GOLD)
        d.text((72, y), str(i), font=font(SERIF_B, 40), fill=GOLD if accent else INK_SOFT)
        d.text((140, y - 4), str(p.get("no", "")), font=font(SANS_B, 64), fill=INK)
        d.text((280, y + 4), p.get("name", ""), font=font(SERIF_B, 42), fill=INK)
        d.text((280, y + 62), p.get("sub", ""), font=font(SANS_R, 24), fill=INK_MUTE)
        d.line([(72, y + 118), (1024, y + 118)], fill=(230, 220, 204), width=1)
        y += 136
    band_top = min(H - 160, y + 20)
    d.rectangle([0, band_top, W, H], fill=TICKER)
    chips = [str(p.get("no", "")) for p in picks[:4]]
    cw, ch, gap = 132, 72, 24
    total = len(chips) * cw + max(0, len(chips) - 1) * gap
    x = (W - total) / 2
    cy = band_top + (H - band_top - ch) / 2
    for n in chips:
        d.rounded_rectangle([x, cy, x + cw, cy + ch], radius=8, fill=(22, 36, 30), outline=GOLD, width=2)
        d.text((x + cw / 2, cy + ch / 2), n, font=font(SANS_B, 34), fill=GOLD3, anchor="mm")
        x += cw + gap
    return save(im, dest)


def render_post(race: dict, dest: str = "tx_poster_post") -> tuple[Path, Path]:
    im = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(im)
    pred = [str(x) for x in (race.get("pred") or [])][:4]
    actual = [str(x) for x in (race.get("actual") or [])][:4]
    hitset = set(pred) & set(actual)
    draw_header(d, "TX-ORACLE天喜引擎 · 預測與賽果比對")
    y0 = draw_meeting(d, race.get("date_line", ""), race.get("race_line", ""), "", hit=f"{len(hitset)}/{max(len(pred), 1)}" if pred else None)
    d.line([(56, y0), (1024, y0)], fill=(220, 208, 190), width=2)
    d.text((200, y0 + 36), "模型首四", font=font(SANS_B, 22), fill=INK_MUTE)
    d.text((760, y0 + 36), "賽果頭四", font=font(SANS_B, 22), fill=INK_MUTE)
    yy = y0 + 90
    for i in range(4):
        a = pred[i] if i < len(pred) else "—"
        b = actual[i] if i < len(actual) else "—"
        d.text((200, yy), a, font=font(SERIF_B, 80), fill=GOLD if a in hitset else INK)
        d.text((760, yy), b, font=font(SERIF_B, 80), fill=GOLD if b in hitset else INK)
        yy += 100
    rows = race.get("payouts") or []
    band_top = min(H - 120, yy + 36)
    d.rectangle([0, band_top, W, H], fill=TICKER)
    y = band_top + 24
    if not rows:
        d.text((W / 2, y + 28), "本場未入表列彩池", font=font(SANS_R, 26), fill=TAN, anchor="mt")
    for row in rows:
        d.text((56, y + 18), f"命中{row['pool']}", font=font(SERIF_B, 30), fill=GOLD3)
        d.text((560, y + 8), "$10一注每注派彩", font=font(SANS_R, 22), fill=TAN)
        d.text((560, y + 42), row["payout"], font=font(SANS_B, 36), fill=(59, 191, 122))
        y += 88
    return save(im, dest)


def tg_send_document(pdf_path: Path, caption: str = "") -> None:
    import json, os, urllib.request
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
        chunks.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n".encode())
        chunks.append(value if isinstance(value, bytes) else str(value).encode())
        chunks.append(b"\r\n")
    field("chat_id", channel)
    field("caption", caption.encode("utf-8"))
    chunks.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"document\"; filename=\"{pdf_path.name}\"\r\nContent-Type: application/pdf\r\n\r\n".encode())
    chunks.append(body_file)
    chunks.append(f"\r\n--{boundary}--\r\n".encode())
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendDocument",
        data=b"".join(chunks),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        resp = json.loads(r.read().decode())
    if not resp.get("ok"):
        raise SystemExit(resp)
