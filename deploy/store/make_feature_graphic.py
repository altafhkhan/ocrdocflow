"""Draws the Google Play "feature graphic" (1024 x 500) from the app logo.

    python deploy/store/make_feature_graphic.py

Needs Pillow. Edit the two text lines below to change the wording.
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
LOGO = HERE.parents[1] / "frontend" / "assets" / "logo.png"
TITLE = "OCRDocFlow"
LINES = ["Scan invoices.", "Check the data.", "Export to CSV or Excel."]
F = "C:/Windows/Fonts/"

W, H = 1024, 500
top, bottom = (16, 32, 96), (37, 99, 235)  # navy to royal blue
img = Image.new("RGB", (W, H))
px = img.load()
for y in range(H):
    t = y / (H - 1)
    row = tuple(round(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
    for x in range(W):
        px[x, y] = row
d = ImageDraw.Draw(img)

# Logo on a white rounded tile, left side.
tile = 300
tx, ty = 80, (H - tile) // 2
d.rounded_rectangle([tx, ty, tx + tile, ty + tile], radius=56, fill="white")
logo = Image.open(LOGO).convert("RGBA")
logo = logo.crop(logo.getbbox())
scale = (tile * 0.78) / max(logo.size)
logo = logo.resize((round(logo.width * scale), round(logo.height * scale)), Image.LANCZOS)
img.paste(logo, (tx + (tile - logo.width) // 2, ty + (tile - logo.height) // 2), logo)

x = tx + tile + 64
d.text((x, 118), TITLE, font=ImageFont.truetype(F + "arialbd.ttf", 84), fill="white")
y = 232
for line in LINES:
    d.text((x, y), line, font=ImageFont.truetype(F + "arial.ttf", 40), fill=(219, 234, 254))
    y += 54

img.save(HERE / "feature-graphic-1024x500.png")
print("wrote feature-graphic-1024x500.png")
