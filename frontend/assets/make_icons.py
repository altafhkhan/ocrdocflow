"""
Makes every app icon and splash image for the Android and iOS apps from
one logo file (frontend/assets/logo.png, the Qumaxa mark on a transparent
background).

Run again whenever the logo changes, then rebuild the apps:

    python frontend/assets/make_icons.py

Needs Pillow (pip install pillow).
"""
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
RES = HERE.parent / "android" / "app" / "src" / "main" / "res"
IOS = HERE.parent / "ios" / "App" / "App" / "Assets.xcassets"
WHITE = (255, 255, 255, 255)

logo = Image.open(HERE / "logo.png").convert("RGBA")
logo = logo.crop(logo.getbbox())  # trim empty edges so sizing is exact


def canvas(width, height, share, background=WHITE):
    """The logo centred on a canvas, its longer side filling `share` of the shorter canvas side."""
    out = Image.new("RGBA", (width, height), background)
    side = min(width, height) * share
    scale = side / max(logo.size)
    mark = logo.resize((round(logo.width * scale), round(logo.height * scale)), Image.LANCZOS)
    out.alpha_composite(mark, ((width - mark.width) // 2, (height - mark.height) // 2))
    return out


def rounded(img, radius_share):
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, img.width - 1, img.height - 1], radius=round(img.width * radius_share), fill=255)
    img.putalpha(mask)
    return img


# --- Android launcher icons
for folder, px in {"mdpi": 48, "hdpi": 72, "xhdpi": 96, "xxhdpi": 144, "xxxhdpi": 192}.items():
    d = RES / f"mipmap-{folder}"
    rounded(canvas(px, px, 0.78), 0.18).save(d / "ic_launcher.png")
    rounded(canvas(px, px, 0.70), 0.5).save(d / "ic_launcher_round.png")
    # Adaptive icon: Android crops the outer part, so the logo stays in the middle.
    fg = round(px * 108 / 48)
    canvas(fg, fg, 0.50, (0, 0, 0, 0)).save(d / "ic_launcher_foreground.png")

# --- Android splash screens (same sizes as the files they replace)
for png in RES.glob("drawable*/splash.png"):
    w, h = Image.open(png).size
    canvas(w, h, 0.40).convert("RGB").save(png)

# --- iOS icon (no transparency allowed) and splash
canvas(1024, 1024, 0.74).convert("RGB").save(IOS / "AppIcon.appiconset" / "AppIcon-512@2x.png")
for png in (IOS / "Splash.imageset").glob("*.png"):
    canvas(2732, 2732, 0.22).convert("RGB").save(png)

# --- Store listing icons
canvas(512, 512, 0.74).save(HERE / "play-store-icon-512.png")
canvas(1024, 1024, 0.74).convert("RGB").save(HERE / "app-store-icon-1024.png")
print("icons and splash screens written")
