#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Аппын icon үүсгэх (PWA / iOS home screen).
Гаралт: static/icons/{favicon-32,apple-touch-icon-180,icon-192,icon-512,icon-maskable-512}.png
Дизайн: брендийн navy дэвсгэр + цаг + ногоон «болоо» тэмдэг (текстгүй, олон хэлэнд тохирно).
"""
from __future__ import annotations
import os
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "static", "icons")

NAVY = (15, 33, 55)
NAVY2 = (23, 50, 79)
GREEN = (22, 163, 74)
WHITE = (255, 255, 255)


def gradient(size: int, c1, c2) -> Image.Image:
    img = Image.new("RGB", (size, size), c1)
    d = ImageDraw.Draw(img)
    for y in range(size):
        t = y / max(1, size - 1)
        d.line([(0, y), (size, y)],
               fill=tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3)))
    return img


def content(size: int) -> Image.Image:
    """Цаг + ногоон тэмдэг — тунгалаг дэвсгэртэй."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    cx = cy = size / 2
    R = size * 0.32
    w = max(2, int(round(size * 0.055)))
    d.ellipse([cx - R, cy - R, cx + R, cy + R], outline=WHITE, width=w)
    d.line([cx, cy, cx, cy - R * 0.58], fill=WHITE, width=w)
    d.line([cx, cy, cx + R * 0.44, cy], fill=WHITE, width=w)
    r2 = max(2, int(size * 0.038))
    d.ellipse([cx - r2, cy - r2, cx + r2, cy + r2], fill=WHITE)
    bx, by, br = size * 0.73, size * 0.73, size * 0.155
    d.ellipse([bx - br, by - br, bx + br, by + br], fill=GREEN)
    lw = max(2, int(round(size * 0.05)))
    d.line([bx - br * 0.46, by + br * 0.03, bx - br * 0.10, by + br * 0.42], fill=WHITE, width=lw)
    d.line([bx - br * 0.10, by + br * 0.42, bx + br * 0.50, by - br * 0.36], fill=WHITE, width=lw)
    return img


def rounded(size: int, radius_ratio: float = 0.22) -> Image.Image:
    """Дугуй булантай icon (Android/iOS-ийн «any» зориулалт)."""
    bg = gradient(size, NAVY2, NAVY).convert("RGBA")
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, size - 1, size - 1],
                                           radius=int(size * radius_ratio), fill=255)
    bg.putalpha(mask)
    bg.alpha_composite(content(size))
    return bg


def maskable(size: int, scale: float = 0.74) -> Image.Image:
    """Maskable: дэвсгэр бүтэн (дугуй/дөрвөлжин mask ч харагдана), агуулга төвд."""
    bg = gradient(size, NAVY2, NAVY).convert("RGBA")
    inner = content(size).resize((int(size * scale), int(size * scale)), Image.LANCZOS)
    bg.alpha_composite(inner, ((size - inner.width) // 2, (size - inner.height) // 2))
    return bg


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    files = {
        "favicon-32.png": rounded(32, 0.24),
        "apple-touch-icon-180.png": rounded(180),
        "icon-192.png": rounded(192),
        "icon-512.png": rounded(512),
        "icon-maskable-512.png": maskable(512),
    }
    for name, img in files.items():
        p = os.path.join(OUT, name)
        img.save(p, "PNG", optimize=True)
        print(f"  ✓ {name:26s} {img.width}×{img.height}  {os.path.getsize(p) / 1024:.1f} KB")


if __name__ == "__main__":
    print("Icon үүсгэж байна…")
    main()
