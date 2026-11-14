import glob, os, re
from PIL import Image, ImageDraw

RES = os.path.expanduser("~/odysseus-apk/android/app/src/main/res")
PWA = os.path.expanduser("~/odysseus-apk/pwa-icons")
BG = (40, 44, 52, 255)  # #282c34, same as PWA background_color/theme_color

logo = Image.open(f"{PWA}/icon-512.png").convert("RGBA")
maskable = Image.open(f"{PWA}/icon-maskable-512.png").convert("RGBA")

def scaled(img, size):
    return img.resize((size, size), Image.LANCZOS)

# Legacy launcher icons (square, and round = circle-masked)
legacy = {"mdpi": 48, "hdpi": 72, "xhdpi": 96, "xxhdpi": 144, "xxxhdpi": 192}
# Adaptive foreground canvas is 108dp: 108 * density factor
fg = {"mdpi": 108, "hdpi": 162, "xhdpi": 216, "xxhdpi": 324, "xxxhdpi": 432}

for d, px in legacy.items():
    base = f"{RES}/mipmap-{d}"
    sq = scaled(maskable, px)
    sq.save(f"{base}/ic_launcher.png")
    mask = Image.new("L", (px, px), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, px - 1, px - 1), fill=255)
    rnd = Image.new("RGBA", (px, px), (0, 0, 0, 0))
    rnd.paste(sq, (0, 0), mask)
    rnd.save(f"{base}/ic_launcher_round.png")

for d, px in fg.items():
    # Logo at ~60% of the canvas keeps it inside the 66% adaptive safe zone
    inner = int(px * 0.60)
    canvas = Image.new("RGBA", (px, px), (0, 0, 0, 0))
    canvas.paste(scaled(logo, inner), ((px - inner) // 2, (px - inner) // 2), scaled(logo, inner))
    canvas.save(f"{RES}/mipmap-{d}/ic_launcher_foreground.png")

# Splash screens: keep each file's size, dark background, centred logo
for path in glob.glob(f"{RES}/drawable*/splash.png"):
    w, h = Image.open(path).size
    side = int(min(w, h) * 0.35)
    canvas = Image.new("RGBA", (w, h), BG)
    canvas.paste(scaled(logo, side), ((w - side) // 2, (h - side) // 2), scaled(logo, side))
    canvas.convert("RGB").save(path)
    print("splash", os.path.relpath(path, RES), w, h)

# Adaptive background colour -> PWA dark colour
bgxml = f"{RES}/values/ic_launcher_background.xml"
s = open(bgxml).read()
s = re.sub(r"#FFFFFF", "#282c34", s)
open(bgxml, "w").write(s)

# Splash theme: dark background so no white/black flash on launch
sty = f"{RES}/values/styles.xml"
s = open(sty).read()
if "windowSplashScreenBackground" not in s:
    s = s.replace(
        '<item name="android:background">@drawable/splash</item>',
        '<item name="android:background">@drawable/splash</item>\n'
        '        <item name="windowSplashScreenBackground">#282c34</item>',
    )
    open(sty, "w").write(s)
print("done")
