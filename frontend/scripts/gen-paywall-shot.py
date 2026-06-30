#!/usr/bin/env python3
"""Render an App Store review screenshot of the PuranGPT Pro paywall (1290x2796)."""
import sys
from PIL import Image, ImageDraw, ImageFont

W, H = 1290, 2796
OUT = sys.argv[1] if len(sys.argv) > 1 else "/tmp/paywall_review.png"

SAFFRON = (255, 153, 51)
GOLD = (255, 218, 117)
GOLD_TEXT = (232, 213, 163)
MUTE = (163, 141, 124)
BG_TOP = (28, 20, 8)
BG_BOT = (13, 10, 4)

img = Image.new("RGB", (W, H), BG_BOT)
draw = ImageDraw.Draw(img)

# Vertical gradient background
for y in range(H):
    t = y / H
    r = int(BG_TOP[0] * (1 - t) + BG_BOT[0] * t)
    g = int(BG_TOP[1] * (1 - t) + BG_BOT[1] * t)
    b = int(BG_TOP[2] * (1 - t) + BG_BOT[2] * t)
    draw.line([(0, y), (W, y)], fill=(r, g, b))

# Soft saffron glow at top center
glow = Image.new("RGB", (W, H), BG_BOT)
gdraw = ImageDraw.Draw(glow)
cx, cy = W // 2, 470
for rad in range(420, 0, -3):
    a = max(0, 1 - rad / 420) * 0.5
    col = (int(BG_BOT[0] + (SAFFRON[0] - BG_BOT[0]) * a),
           int(BG_BOT[1] + (SAFFRON[1] - BG_BOT[1]) * a),
           int(BG_BOT[2] + (SAFFRON[2] - BG_BOT[2]) * a))
    gdraw.ellipse([cx - rad, cy - rad, cx + rad, cy + rad], fill=col)
img = Image.blend(img, glow, 0.45)
draw = ImageDraw.Draw(img)


def font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()


SERIF = "/System/Library/Fonts/Supplemental/Baskerville.ttc"
UI = "/System/Library/Fonts/Helvetica.ttc"
f_title = font(SERIF, 96)
f_sub = font(UI, 40)
f_feat = font(UI, 46)
f_price = font(SERIF, 72)
f_small = font(UI, 34)
f_cta = font(UI, 54)


def center(text, y, fnt, fill):
    w = draw.textlength(text, font=fnt)
    draw.text(((W - w) / 2, y), text, font=fnt, fill=fill)


# Emblem (sun/star)
sx, sy, sr = W // 2, 360, 90
for i in range(12):
    import math
    ang = i * math.pi / 6
    draw.line([sx + math.cos(ang) * 50, sy + math.sin(ang) * 50,
               sx + math.cos(ang) * sr, sy + math.sin(ang) * sr],
              fill=GOLD, width=6)
draw.ellipse([sx - 46, sy - 46, sx + 46, sy + 46], outline=SAFFRON, width=8)

center("Unlock PuranGPT Pro", 540, f_title, (255, 255, 255))
center("Full access to ancient wisdom, unlimited", 670, f_sub, MUTE)

features = [
    "Unlimited questions, every day",
    "Deep Research — web-grounded synthesis",
    "Cited verses from every sacred text",
    "English, Hindi & Russian",
    "Priority responses & API access",
]
fy = 820
for feat in features:
    cxb = 210
    draw.ellipse([cxb - 26, fy + 6, cxb + 26, fy + 58], outline=SAFFRON, width=4)
    draw.line([cxb - 12, fy + 32, cxb - 2, fy + 44], fill=SAFFRON, width=5)
    draw.line([cxb - 2, fy + 44, cxb + 16, fy + 18], fill=SAFFRON, width=5)
    draw.text((cxb + 60, fy), feat, font=f_feat, fill=GOLD_TEXT)
    fy += 110

# Plan cards
card_y = 1480
for i, (label, price, note) in enumerate([
    ("Monthly", "$11.11", "/month"),
    ("Annual", "$92.59", "/year  ·  Save 17%"),
]):
    cx0, cx1 = 150, W - 150
    cy0 = card_y + i * 220
    cy1 = cy0 + 180
    sel = (i == 1)
    draw.rounded_rectangle([cx0, cy0, cx1, cy1], radius=36,
                           outline=SAFFRON if sel else (90, 78, 60),
                           width=6 if sel else 3,
                           fill=(40, 30, 14) if sel else (24, 20, 12))
    draw.text((cx0 + 60, cy0 + 50), label, font=f_feat, fill=(255, 255, 255))
    pw = draw.textlength(price, font=f_price)
    draw.text((cx1 - pw - 60, cy0 + 40), price, font=f_price, fill=SAFFRON)
    draw.text((cx0 + 60, cy0 + 115), note, font=f_small, fill=MUTE)

# CTA button
by0, by1 = 1960, 2110
draw.rounded_rectangle([150, by0, W - 150, by1], radius=44, fill=SAFFRON)
ctaw = draw.textlength("Subscribe", font=f_cta)
draw.text(((W - ctaw) / 2, by0 + 44), "Subscribe", font=f_cta, fill=(19, 19, 19))

center("Cancel anytime in Settings.", 2200, f_small, MUTE)
center("Recurring billing · Auto-renews until cancelled", 2260, f_small, MUTE)

img.save(OUT, "PNG")
print("wrote", OUT, img.size)
