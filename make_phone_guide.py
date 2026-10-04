#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Утсанд суулгах заавар — А4 2 хуудас (iPhone/Safari + Android/Chrome), зурагтай.

    pip install segno pillow
    python3 make_phone_guide.py --url https://таны-хаяг.onrender.com

Гаралт: exports/phone_install_guide.pdf  (хэвлэхэд бэлэн)
        exports/phone_install_ios.png    (Viber/WhatsApp-аар илгээх)
        exports/phone_install_android.png
"""
from __future__ import annotations
import argparse, io, os, sys
from PIL import Image, ImageDraw, ImageFont

try:
    import segno
except ImportError:
    sys.exit("segno сан байхгүй: pip install segno pillow")

HERE = os.path.dirname(os.path.abspath(__file__))
DPI = 200
W, H = int(8.27 * DPI), int(11.69 * DPI)
NAVY, NAVY2 = (15, 33, 55), (23, 50, 79)
GREEN, BLUE = (22, 163, 74), (47, 85, 151)
RED = (200, 30, 30)
INK, MUTED, LINE = (15, 23, 42), (100, 116, 139), (203, 213, 225)
AMBER_BG, AMBER_TX = (255, 247, 230), (138, 82, 9)
CARD_BG = (248, 250, 252)
ICON = os.path.join(HERE, "static", "icons", "icon-192.png")

FONTS = {
    "bold": ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
             "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
             "C:/Windows/Fonts/arialbd.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf"],
    "reg": ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "C:/Windows/Fonts/arial.ttf", "/System/Library/Fonts/Supplemental/Arial.ttf"],
    "mono": ["/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
             "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
             "C:/Windows/Fonts/consola.ttf"],
}


def F(kind, inches):  # фонт (инчээр)
    px = max(9, int(inches * DPI))
    for p in FONTS[kind]:
        if os.path.isfile(p):
            return ImageFont.truetype(p, px)
    return ImageFont.load_default()


def qr_img(url, px):
    buf = io.BytesIO()
    segno.make(url, error="h").save(buf, kind="png", scale=11, border=1, dark="#0f2137", light="#ffffff")
    buf.seek(0)
    return Image.open(buf).convert("RGB").resize((px, px), Image.NEAREST)


def badge(d, x, y, n, r):  # дугаартай улаан тэмдэг
    d.ellipse([x - r, y - r, x + r, y + r], fill=RED, outline=(255, 255, 255), width=max(2, r // 6))
    f = F("bold", r / DPI / 1.35)
    b = d.textbbox((0, 0), str(n), font=f)
    d.text((x - (b[2] - b[0]) / 2, y - (b[3] - b[1]) / 2 - r * 0.12), str(n), font=f, fill=(255, 255, 255))


def phone(d, x, y, w, h, screen=(255, 255, 255)):  # утасны хүрээ
    d.rounded_rectangle([x, y, x + w, y + h], radius=int(w * 0.13), fill=(30, 41, 59))
    px, py = int(w * 0.055), int(h * 0.028)
    d.rounded_rectangle([x + px, y + py, x + w - px, y + h - py], radius=int(w * 0.10), fill=screen)
    return (x + px, y + py, x + w - px, y + h - py)


def bars(d, x, y, w, n, gap, h=9, fill=(226, 232, 240)):  # текст орлуулах саарал мөр
    for i in range(n):
        ww = w if i % 3 != 2 else int(w * 0.62)
        d.rounded_rectangle([x, y + i * (h + gap), x + ww, y + i * (h + gap) + h], radius=h // 2, fill=fill)


def app_header(d, x, y, w, h=42):  # аппын navy толгой
    d.rounded_rectangle([x, y, x + w, y + h], radius=10, fill=NAVY)
    d.ellipse([x + 10, y + h / 2 - 7, x + 24, y + h / 2 + 7], fill=(255, 255, 255))
    d.rounded_rectangle([x + 32, y + h / 2 - 5, x + w - 14, y + h / 2 + 5], radius=5, fill=(70, 100, 140))


# ─────────────────────────── ЗУРГУУД ───────────────────────────
def m_safari(url):
    """Safari — доод мөрний Хуваалцах товчийг заана."""
    img = Image.new("RGB", (520, 760), (255, 255, 255))
    d = ImageDraw.Draw(img)
    sx, sy, sw, sh = phone(d, 20, 12, 480, 736)
    app_header(d, sx + 14, sy + 16, sw - 28)
    d.rounded_rectangle([sx + 30, sy + 78, sx + sw - 30, sy + 108], radius=8, fill=(241, 245, 249), outline=LINE)
    d.rounded_rectangle([sx + 30, sy + 120, sx + sw - 30, sy + 150], radius=8, fill=(241, 245, 249), outline=LINE)
    d.rounded_rectangle([sx + 30, sy + 164, sx + sw - 30, sy + 202], radius=9, fill=BLUE)
    bars(d, sx + 30, sy + 224, sw - 60, 5, 12)
    # доод toolbar
    tb_y = sy + sh - 54
    d.rounded_rectangle([sx + 12, tb_y, sx + sw - 12, sy + sh - 10], radius=16, fill=(241, 245, 249), outline=LINE)
    cy = (tb_y + sy + sh - 10) / 2
    d.polygon([(sx + 46, cy), (sx + 60, cy - 9), (sx + 60, cy + 9)], fill=(148, 163, 184))
    d.polygon([(sx + 106, cy), (sx + 92, cy - 9), (sx + 92, cy + 9)], fill=(148, 163, 184))
    # share icon (дээш сумтай дөрвөлжин) — улаанаар онцолсон
    shx = sx + 168
    d.rounded_rectangle([shx, cy - 4, shx + 20, cy + 16], radius=5, outline=RED, width=3)
    d.line([shx + 10, cy - 18, shx + 10, cy - 2], fill=RED, width=3)
    d.polygon([(shx + 10, cy - 24), (shx + 4, cy - 15), (shx + 16, cy - 15)], fill=RED)
    d.rounded_rectangle([sx + 226, cy - 10, sx + 262, cy + 12], radius=5, outline=(148, 163, 184), width=3)
    d.rounded_rectangle([sx + 282, cy - 10, sx + 300, cy + 12], radius=5, outline=(148, 163, 184), width=3)
    d.rounded_rectangle([sx + 320, cy - 10, sx + 338, cy + 12], radius=5, outline=(148, 163, 184), width=3)
    badge(d, shx + 30, cy - 34, 1, 20)
    return img


def m_share_sheet():
    """iOS share sheet — «Add to Home Screen» мөрийг заана."""
    img = Image.new("RGB", (520, 760), (255, 255, 255))
    d = ImageDraw.Draw(img)
    x, y, w = 24, 250, 472
    d.rounded_rectangle([x, y, x + w, y + 470], radius=26, fill=(246, 248, 251), outline=LINE, width=2)
    d.rounded_rectangle([x + w / 2 - 40, y + 14, x + w / 2 + 40, y + 20], radius=3, fill=(203, 213, 225))
    # апп icon-уудын эгнээ
    for i in range(4):
        d.rounded_rectangle([x + 30 + i * 92, y + 40, x + 30 + i * 92 + 64, y + 104], radius=15, fill=(226, 232, 240))
    # үйлдлүүдийн жагсаалт
    for i in range(5):
        ry = y + 128 + i * 62
        d.rounded_rectangle([x + 18, ry, x + w - 18, ry + 52], radius=12, fill=(255, 255, 255), outline=LINE)
        if i == 2:  # ← онцолсон мөр
            d.rounded_rectangle([x + 18, ry, x + w - 18, ry + 52], radius=12, fill=(232, 240, 254), outline=BLUE, width=3)
            d.rounded_rectangle([x + 32, ry + 15, x + 54, ry + 37], radius=5, outline=BLUE, width=3)
            d.line([x + 43, ry + 20, x + 43, ry + 32], fill=BLUE, width=3)
            d.line([x + 37, ry + 26, x + 49, ry + 26], fill=BLUE, width=3)
            d.text((x + 70, ry + 14), "Add to Home Screen", font=F("bold", 0.155), fill=BLUE)
        else:
            bars(d, x + 32, ry + 21, int(w * 0.42), 1, 0, h=12)
    badge(d, x + w - 40, y + 128 + 2 * 62 - 12, 2, 22)
    return img


def m_add_dialog(url):
    """iOS «Add to Home Screen» цонх — Add товчийг заана."""
    img = Image.new("RGB", (520, 760), (255, 255, 255))
    d = ImageDraw.Draw(img)
    x, y, w, h = 60, 300, 400, 300
    d.rounded_rectangle([x, y, x + w, y + h], radius=26, fill=(242, 244, 247), outline=LINE, width=2)
    d.text((x + 26, y + 22), "Add to Home Screen", font=F("bold", 0.16), fill=INK)
    d.rounded_rectangle([x + 26, y + 66, x + w - 26, y + 112], radius=10, fill=(255, 255, 255), outline=LINE)
    ic = Image.open(ICON).convert("RGB").resize((30, 30))
    img.paste(ic, (x + 36, y + 74))
    d.rounded_rectangle([x + 76, y + 82, x + w - 40, y + 96], radius=7, fill=(226, 232, 240))
    d.text((x + 26, y + 132), "icon нэр", font=F("reg", 0.13), fill=MUTED)
    d.line([x, y + 176, x + w, y + 176], fill=LINE, width=2)
    d.line([x + w / 2, y + 176, x + w / 2, y + 234], fill=LINE, width=2)
    d.text((x + 74, y + 196), "Cancel", font=F("reg", 0.155), fill=MUTED)
    d.rounded_rectangle([x + w / 2 + 52, y + 186, x + w / 2 + 118, y + 226], radius=10, fill=BLUE)
    d.text((x + w / 2 + 66, y + 196), "Add", font=F("bold", 0.155), fill=(255, 255, 255))
    d.text((x + 26, y + 244), url.replace("https://", ""), font=F("mono", 0.105), fill=(148, 163, 184))
    badge(d, x + w / 2 + 138, y + 182, 3, 22)
    return img


def m_home_screen(caption_icon=True):
    """Home screen — апп icon гарч ирсэн байдал."""
    img = Image.new("RGB", (520, 760), (255, 255, 255))
    d = ImageDraw.Draw(img)
    sx, sy, sw, sh = phone(d, 20, 12, 480, 736)
    d.rounded_rectangle([sx, sy, sx + sw, sy + int(sh * 0.42)], radius=20,
                        fill=(226, 234, 244))
    for r in range(3):
        for c in range(4):
            gx = sx + 34 + c * 100
            gy = sy + 30 + r * 100
            d.rounded_rectangle([gx, gy, gx + 72, gy + 72], radius=17, fill=(203, 213, 225))
    ic = Image.open(ICON).convert("RGB").resize((72, 72))
    hx, hy = sx + 34, sy + 214
    img.paste(ic, (hx, hy))
    d.rounded_rectangle([hx - 6, hy - 6, hx + 78, hy + 78], radius=20, outline=GREEN, width=4)
    f = F("bold", 0.115)
    lbl = "Цаг бүртгэл"
    b = d.textbbox((0, 0), lbl, font=f)
    d.text((hx + 36 - (b[2] - b[0]) / 2, hy + 86), lbl, font=f, fill=INK)
    d.rounded_rectangle([sx + 24, sy + sh - 60, sx + sw - 24, sy + sh - 36], radius=12, fill=(241, 245, 249), outline=LINE)
    for c in range(4):
        d.rounded_rectangle([sx + 50 + c * 100, sy + sh - 54, sx + 50 + c * 100 + 40, sy + sh - 42], radius=6, fill=(203, 213, 225))
    badge(d, hx + 82, hy - 2, 4, 20)
    return img


def m_chrome(url):
    """Chrome — баруун дээд ⋮ цэсийг заана."""
    img = Image.new("RGB", (520, 760), (255, 255, 255))
    d = ImageDraw.Draw(img)
    sx, sy, sw, sh = phone(d, 20, 12, 480, 736)
    # Chrome-ийн хаягийн мөр (дээд талд)
    d.rounded_rectangle([sx + 14, sy + 16, sx + sw - 14, sy + 78], radius=14, fill=(241, 245, 249), outline=LINE)
    d.ellipse([sx + 28, sy + 34, sx + 46, sy + 52], fill=(66, 133, 244))
    d.rounded_rectangle([sx + 56, sy + 36, sx + sw - 90, sy + 52], radius=8, fill=(226, 232, 240))
    # ⋮ цэс
    for i in range(3):
        d.ellipse([sx + sw - 56, sy + 28 + i * 16, sx + sw - 44, sy + 40 + i * 16], fill=RED)
    badge(d, sx + sw - 26, sy + 24, 1, 20)
    app_header(d, sx + 14, sy + 92, sw - 28)
    d.rounded_rectangle([sx + 30, sy + 150, sx + sw - 30, sy + 180], radius=8, fill=(241, 245, 249), outline=LINE)
    d.rounded_rectangle([sx + 30, sy + 192, sx + sw - 30, sy + 230], radius=9, fill=BLUE)
    bars(d, sx + 30, sy + 252, sw - 60, 5, 12)
    return img


def m_chrome_menu():
    """Chrome ⋮ цэс — «Add to Home screen / Install app» мөрийг заана."""
    img = Image.new("RGB", (520, 760), (255, 255, 255))
    d = ImageDraw.Draw(img)
    x, y, w = 150, 90, 354
    d.rounded_rectangle([x, y, x + w, y + 560], radius=18, fill=(255, 255, 255), outline=LINE, width=2)
    rows = [("New tab", False), ("History", False), ("Downloads", False),
            ("Add to Home screen", True), ("Share", False), ("Settings", False)]
    for i, (_, hl) in enumerate(rows):
        ry = y + 18 + i * 88
        if hl:
            d.rounded_rectangle([x + 10, ry, x + w - 10, ry + 72], radius=12, fill=(232, 240, 254), outline=BLUE, width=3)
            d.rounded_rectangle([x + 26, ry + 26, x + 46, ry + 46], radius=5, outline=BLUE, width=3)
            d.line([x + 36, ry + 30, x + 36, ry + 42], fill=BLUE, width=3)
            d.text((x + 60, ry + 20), "Add to Home screen", font=F("bold", 0.135), fill=BLUE)
            d.text((x + 60, ry + 46), "эсвэл Install app", font=F("reg", 0.115), fill=MUTED)
            badge(d, x + w - 34, ry - 10, 2, 22)
        else:
            bars(d, x + 26, ry + 30, int(w * 0.4), 1, 0, h=13)
    return img


def m_install_dialog(url):
    """Chrome «Install app» цонх — Install товчийг заана."""
    img = Image.new("RGB", (520, 760), (255, 255, 255))
    d = ImageDraw.Draw(img)
    x, y, w, h = 44, 250, 432, 330
    d.rounded_rectangle([x, y, x + w, y + h], radius=24, fill=(248, 250, 252), outline=LINE, width=2)
    ic = Image.open(ICON).convert("RGB").resize((72, 72))
    img.paste(ic, (int(x + w / 2 - 36), y + 26))
    f = F("bold", 0.17)
    t = "Install app"
    b = d.textbbox((0, 0), t, font=f)
    d.text((x + w / 2 - (b[2] - b[0]) / 2, y + 112), t, font=f, fill=INK)
    for i in range(2):
        d.rounded_rectangle([x + 40, y + 152 + i * 30, x + w - 40, y + 168 + i * 30], radius=8, fill=(226, 232, 240))
    d.text((x + 40, y + 218), url.replace("https://", ""), font=F("mono", 0.105), fill=(148, 163, 184))
    d.line([x, y + 250, x + w, y + 250], fill=LINE, width=2)
    d.text((x + 62, y + 272), "Cancel", font=F("reg", 0.155), fill=MUTED)
    d.rounded_rectangle([x + w / 2 + 34, y + 262, x + w / 2 + 132, y + 304], radius=10, fill=GREEN)
    d.text((x + w / 2 + 58, y + 272), "Install", font=F("bold", 0.155), fill=(255, 255, 255))
    badge(d, x + w / 2 + 150, y + 258, 3, 22)
    return img


# ─────────────────────────── ХУУДАС ───────────────────────────
def wrap(d, text, f, max_px):
    """Текстийг өгөгдсөн өргөнд багтах хэдэн мөрөнд хуваана."""
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if d.textlength(t, font=f) <= max_px or not cur:
            cur = t
        else:
            lines.append(cur); cur = w
    if cur:
        lines.append(cur)
    return lines


def page(platform: str, url: str, company: str, steps, tips) -> Image.Image:
    img = Image.new("RGB", (W, H), (255, 255, 255))
    d = ImageDraw.Draw(img)
    M = 0.42 * DPI                       # захын зай
    top = int(1.85 * DPI)                # толгойн өндөр

    # ── Толгой ──
    for y in range(top):
        t = y / top
        d.line([(0, y), (W, y)], fill=tuple(int(NAVY2[i] + (NAVY[i] - NAVY2[i]) * t) for i in range(3)))
    d.text((M, 0.34 * DPI), company, font=F("bold", 0.25), fill=(255, 255, 255))
    d.text((M, 0.68 * DPI), "ЦАГ БҮРТГЭЛ БА ИРЦИЙН СИСТЕМ", font=F("reg", 0.142), fill=(201, 216, 234))
    d.text((M, 0.96 * DPI), f"Утсанд суулгах — {platform}", font=F("bold", 0.30), fill=(255, 255, 255))
    d.text((M, 1.38 * DPI), "4 алхам · 1 минут · дараа нь нэг товчоор нэвтэрнэ",
           font=F("reg", 0.152), fill=(186, 205, 228))
    qpx = int(0.98 * DPI)
    qi = qr_img(url, qpx)
    qx, qy = W - qpx - int(M), int(0.38 * DPI)
    img.paste(qi, (qx, qy))
    d.text((qx - 2, qy + qpx + 10), "хаяг", font=F("reg", 0.108), fill=(201, 216, 234))

    # ── Алхмууд (текстийг халиахгүй, картын өндөр автоматаар) ──
    FIG_W = 1.42 * DPI
    txt_w = W - 2 * M - 0.34 * DPI - FIG_W - 0.18 * DPI
    f_title, f_body = F("bold", 0.195), F("reg", 0.148)
    lh = 0.225 * DPI
    y = top + 0.20 * DPI
    for i, step in enumerate(steps):
        title, body = step[0], step[1]
        fig = step[2] if len(step) > 2 else None
        lines = []
        for para in body:
            lines += wrap(d, para, f_body, txt_w)
        card_h = 0.16 * DPI + 0.28 * DPI + len(lines) * lh + 0.14 * DPI
        fig_h = min(card_h - 0.22 * DPI, FIG_W * 760 / 520)
        card_h = max(card_h, fig_h + 0.22 * DPI)
        d.rounded_rectangle([M, y, W - M, y + card_h], radius=int(0.15 * DPI), fill=CARD_BG, outline=LINE)
        # зураг (баруун)
        if fig is not None:
            fimg = fig.copy()
            fimg.thumbnail((FIG_W, fig_h), Image.LANCZOS)
            img.paste(fimg, (int(W - M - 0.12 * DPI - fimg.width), int(y + (card_h - fimg.height) / 2)))
        # текст (зүүн)
        tx = M + 0.24 * DPI
        badge(d, tx + 0.13 * DPI, y + 0.30 * DPI, i + 1, int(0.165 * DPI))
        d.text((tx + 0.36 * DPI, y + 0.18 * DPI), title, font=f_title, fill=INK)
        yy = y + 0.50 * DPI
        for ln in lines:
            d.text((tx + 0.36 * DPI, yy), ln, font=f_body, fill=(51, 65, 85))
            yy += lh
        y += card_h + 0.10 * DPI

    # ── Анхаарах ──
    tlines = []
    for para in tips:
        tlines += wrap(d, para, F("reg", 0.142), W - 2 * M - 0.44 * DPI)
    box_h = 0.36 * DPI + len(tlines) * 0.222 * DPI + 0.10 * DPI
    ty = min(y + 0.06 * DPI, H - 0.78 * DPI - box_h)
    d.rounded_rectangle([M, ty, W - M, ty + box_h], radius=int(0.13 * DPI), fill=AMBER_BG, outline=(243, 217, 166))
    d.text((M + 0.26 * DPI, ty + 0.14 * DPI), "⚠  АНХААРАХ", font=F("bold", 0.16), fill=AMBER_TX)
    yy = ty + 0.44 * DPI
    for ln in tlines:
        d.text((M + 0.26 * DPI, yy), ln, font=F("reg", 0.142), fill=(120, 72, 8))
        yy += 0.222 * DPI

    # ── Хөл ──
    d.line([(M, H - 0.68 * DPI), (W - M, H - 0.68 * DPI)], fill=LINE, width=2)
    d.text((M, H - 0.57 * DPI), "Нэвтрэх: ажилтны код (EMP…) + 4 оронтой ПИН — бригадир өгнө.",
           font=F("reg", 0.145), fill=MUTED)
    d.text((M, H - 0.38 * DPI), f"© {company} · Цаг бүртгэлийн систем v4.6 · Монгол интерфэйс",
           font=F("reg", 0.13), fill=(148, 163, 184))
    return img


def main() -> None:
    ap = argparse.ArgumentParser(description="Утсанд суулгах заавар (A4, 2 хуудас)")
    ap.add_argument("--url", default="https://attendance-system.onrender.com")
    ap.add_argument("--company", default="Барилгын Бригад ХХК")
    ap.add_argument("--out", default=os.path.join(HERE, "exports"))
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    u = a.url.rstrip("/")
    host = u.replace("https://", "").replace("http://", "")

    ios = page(
        "iPhone (Safari)", u, a.company,
        [
            ("Safari-аар хаягийг нээнэ", [
                "Утсандаа Safari хөтчийг нээгээд хаягийг бичнэ:",
                host,
                "эсвэл зүүн талын QR-ыг камераараа уншуулна.",
                "⚠ Chrome биш, Safari байх ёстой."], m_safari(u)),
            ("Хуваалцах товчийг дарна", [
                "Доод мөрний дунд байгаа «□↑ Хуваалцах» (Share)",
                "товчийг дарна. Хаягийн мөр дээд талд байвал",
                "баруун талын □↑ товчийг дарна."], m_share_sheet()),
            ("«Add to Home Screen» сонгоно", [
                "Нээгдсэн цэснээс доош гүйлгээд",
                "«Add to Home Screen» («Дэлгэцэнд нэмэх») мөрийг",
                "дарна. Цэс урт бол доошоо гүйлгэнэ үү."], m_add_dialog(u)),
            ("«Add» дарж дуусгана", [
                "Баруун дээд «Add» («Нэмэх») товчийг дарна.",
                "Дэлгэцэн дээр ЦАГ icon гарна → цаашид",
                "түүгээрээ нэвтэрнэ."], m_home_screen()),
        ],
        ["Анх нээхэд «Камер/Байршил зөвшөөрөх үү?» гэж асууна → ЗӨВШӨӨРӨХ дарна (ирц бүртгэхэд зайлшгүй).",
         "Татгалзсан бол: Safari → «Aa» → Вэбсайтын тохиргоо → Камер/Байршил → Зөвшөөрөх.",
         "Хуучин хувилбар харагдвал хуудсыг доош татаж сэргээнэ, эсвэл icon-оо дахин суулгана."],
    )

    android = page(
        "Android (Chrome)", u, a.company,
        [
            ("Chrome-оор хаягийг нээнэ", [
                "Утсандаа Chrome хөтчийг нээгээд хаягийг бичнэ:",
                host,
                "эсвэл зүүн талын QR-ыг камераараа уншуулна."], m_chrome(u)),
            ("⋮ цэсийг дарна", [
                "Баруун дээд булангийн 3 цэг (⋮) товчийг дарна.",
                "Цэс баруун талаас доошоо нээгдэнэ."], m_chrome_menu()),
            ("«Add to Home screen / Install app»", [
                "Цэснээс «Add to Home screen» эсвэл",
                "«Install app» мөрийг дарна.",
                "(Samsung Internet: ⋮ → Add page to → Home screen)"], m_install_dialog(u)),
            ("«Install» дарж дуусгана", [
                "«Install» (эсвэл «Add») товчийг дарна.",
                "Дэлгэцэн дээр ЦАГ icon гарна → цаашид",
                "түүгээрээ нэвтэрнэ. Интернэт муу үед ч",
                "нэвтрэх хуудас нээгдэнэ."], m_home_screen()),
        ],
        ["Анх нээхэд «Камер/Байршил зөвшөөрөх үү?» гэж асууна → ЗӨВШӨӨРӨХ дарна (ирц бүртгэхэд зайлшгүй).",
         "Татгалзсан бол: Chrome ⋮ → Тохиргоо → Site settings → Camera / Location → Зөвшөөрөх.",
         "Хуучин хувилбар харагдвал хуудсыг доош татаж сэргээнэ, эсвэл icon-оо дахин суулгана."],
    )

    pdf = os.path.join(a.out, "phone_install_guide.pdf")
    png_ios = os.path.join(a.out, "phone_install_ios.png")
    png_and = os.path.join(a.out, "phone_install_android.png")
    ios.save(png_ios, "PNG", optimize=True)
    android.save(png_and, "PNG", optimize=True)
    ios.save(pdf, "PDF", resolution=DPI, save_all=True, append_images=[android])
    print(f"✓ {pdf}   (A4, 2 хуудас)")
    print(f"✓ {png_ios}")
    print(f"✓ {png_and}")
    print(f"  Хаяг: {u}")


if __name__ == "__main__":
    main()
