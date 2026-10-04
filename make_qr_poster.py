#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
QR постер үүсгэгч — «Утсаараа ирцээ бүртгүүлэх» А4 хуудас.

Хэрэглээ (админы компьютер дээр, нэг удаа):
    pip install segno pillow
    python3 make_qr_poster.py --url https://attendance-system-xxxx.onrender.com

Гаралт: exports/qr_poster.pdf   (А4, хэвлэхэд бэлэн)  +  exports/qr_poster.png

Постерыг ажлын байрны хаалган дээр (эсвэл бригадирын өрөөнд) наана.
Ажилтан QR-ыг уншуулаад шууд нээгдэнэ → «Add to Home Screen» → icon болж сууна.

⚠️ Энэ нь серверийн хэсэг БИШ — зөвхөн нэг удаа ажиллуулах хэрэгсэл.
   (Сервер өөрөө гадаад сан шаарддаггүй хэвээр.)
"""
from __future__ import annotations
import argparse
import os
import sys

from PIL import Image, ImageDraw, ImageFont

try:
    import segno
except ImportError:
    sys.exit("segno сан байхгүй: pip install segno pillow")

HERE = os.path.dirname(os.path.abspath(__file__))
DPI = 200
W, H = int(8.27 * DPI), int(11.69 * DPI)          # A4 портрет
NAVY, NAVY2 = (15, 33, 55), (23, 50, 79)
GREEN = (22, 163, 74)
INK = (15, 23, 42)
MUTED = (100, 116, 139)
LINE = (203, 213, 225)

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


def font(kind: str, size: int) -> ImageFont.FreeTypeFont:
    for p in FONTS[kind]:
        if os.path.isfile(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def center_text(d: ImageDraw.ImageDraw, y: int, text: str, f, fill, width: int) -> int:
    box = d.textbbox((0, 0), text, font=f)
    d.text(((width - (box[2] - box[0])) / 2, y), text, font=f, fill=fill)
    return y + (box[3] - box[1])


def build(url: str, company: str, title: str, out_dir: str) -> tuple[str, str]:
    img = Image.new("RGB", (W, H), (255, 255, 255))
    d = ImageDraw.Draw(img)

    # ── Толгойн зурвас ──
    top_h = int(2.05 * DPI)
    for y in range(top_h):
        t = y / top_h
        d.line([(0, y), (W, y)], fill=tuple(int(NAVY2[i] + (NAVY[i] - NAVY2[i]) * t) for i in range(3)))
    d.text((0.55 * DPI, 0.42 * DPI), company, font=font("bold", int(0.30 * DPI)), fill=(255, 255, 255))
    d.text((0.55 * DPI, 0.86 * DPI), "ЦАГ БҮРТГЭЛ БА ИРЦИЙН СИСТЕМ",
           font=font("reg", int(0.17 * DPI)), fill=(201, 216, 234))
    d.line([(0.55 * DPI, 1.42 * DPI), (W - 0.55 * DPI, 1.42 * DPI)], fill=(255, 255, 255, 40), width=2)
    d.text((0.55 * DPI, 1.52 * DPI), title, font=font("bold", int(0.34 * DPI)), fill=(255, 255, 255))

    # ── QR (алдаа засах түвшин H — хэсэг битүү ч уншигдана) ──
    qr = segno.make(url, error="h")
    qr_px = int(3.5 * DPI)
    qr_img = qr.png_as_base64_str(scale=1) if False else None  # (PIL руу шууд зурах)
    import io
    buf = io.BytesIO()
    qr.save(buf, kind="png", scale=11, border=2, dark="#0f2137", light="#ffffff")
    buf.seek(0)
    qi = Image.open(buf).convert("RGB")
    qi = qi.resize((qr_px, qr_px), Image.NEAREST)

    qx = (W - qr_px) // 2
    qy = int(2.55 * DPI)
    pad = int(0.28 * DPI)
    d.rounded_rectangle([qx - pad, qy - pad, qx + qr_px + pad, qy + qr_px + pad],
                        radius=int(0.18 * DPI), fill=(255, 255, 255), outline=LINE, width=3)
    img.paste(qi, (qx, qy))

    # ── Хаяг ──
    y = qy + qr_px + pad + int(0.30 * DPI)
    y = center_text(d, y, "1. Камераараа QR-ыг уншуулна", font("reg", int(0.20 * DPI)), MUTED, W) + int(0.16 * DPI)
    y = center_text(d, y, url, font("mono", int(0.19 * DPI)), INK, W) + int(0.42 * DPI)

    # ── 3 алхам ──
    steps = [
        ("1", "Утсаараа QR-ыг уншуулж, хаягийг нээнэ", "iPhone: Safari · Android: Chrome"),
        ("2", "«Add to Home Screen» дарж icon болгоно",
         "iPhone: Хуваалцах (□↑) → Add to Home Screen · Android: ⋮ → Install app"),
        ("3", "Ажлын байрандаа ирээд «Ажилд орох» дарна",
         "Зураг авч, GPS-ээр байршлаа баталгаажуулна"),
    ]
    sy = y
    for num, t1, t2 in steps:
        cx, cy = int(0.95 * DPI), sy + int(0.20 * DPI)
        d.ellipse([cx - int(0.19 * DPI), cy - int(0.19 * DPI), cx + int(0.19 * DPI), cy + int(0.19 * DPI)], fill=GREEN)
        nb = d.textbbox((0, 0), num, font=font("bold", int(0.21 * DPI)))
        d.text((cx - (nb[2] - nb[0]) / 2, cy - (nb[3] - nb[1]) / 2 - int(0.02 * DPI)), num,
               font=font("bold", int(0.21 * DPI)), fill=(255, 255, 255))
        d.text((1.30 * DPI, sy + int(0.06 * DPI)), t1, font=font("bold", int(0.215 * DPI)), fill=INK)
        d.text((1.30 * DPI, sy + int(0.38 * DPI)), t2, font=font("reg", int(0.165 * DPI)), fill=MUTED)
        sy += int(0.78 * DPI)
        if num != "3":
            d.line([(1.30 * DPI, sy - int(0.10 * DPI)), (W - 0.55 * DPI, sy - int(0.10 * DPI))], fill=(241, 245, 249), width=2)

    # ── Хөлийн мөр ──
    fy = H - int(1.15 * DPI)
    d.line([(0.55 * DPI, fy), (W - 0.55 * DPI, fy)], fill=LINE, width=2)
    d.text((0.55 * DPI, fy + int(0.16 * DPI)),
           "Код, ПИН-ээ мартсан бол бригадир/админд хандана уу.  Зураг нь зөвхөн таны бүртгэлд харагдана.",
           font=font("reg", int(0.16 * DPI)), fill=MUTED)
    d.text((0.55 * DPI, fy + int(0.52 * DPI)), f"© {company} · Цаг бүртгэлийн систем v4.6 · Монгол интерфэйс",
           font=font("reg", int(0.145 * DPI)), fill=(148, 163, 184))

    os.makedirs(out_dir, exist_ok=True)
    png = os.path.join(out_dir, "qr_poster.png")
    pdf = os.path.join(out_dir, "qr_poster.pdf")
    img.save(png, "PNG", optimize=True)
    img.save(pdf, "PDF", resolution=DPI)
    return png, pdf


def main() -> None:
    ap = argparse.ArgumentParser(description="Ажилтны QR постер (A4) үүсгэх")
    ap.add_argument("--url", default="https://attendance-system.onrender.com",
                    help="Аппын хаяг (Render-ийн хаягаа тавина)")
    ap.add_argument("--company", default="Барилгын Бригад ХХК")
    ap.add_argument("--title", default="Утсаараа ирцээ бүртгүүлэх")
    ap.add_argument("--out", default=os.path.join(HERE, "exports"))
    a = ap.parse_args()
    png, pdf = build(a.url, a.company, a.title, a.out)
    print(f"✓ {pdf}  (А4, 200 dpi — хэвлэхэд бэлэн)")
    print(f"✓ {png}")
    print(f"  Хаяг: {a.url}")


if __name__ == "__main__":
    main()
