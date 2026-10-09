"""Seamless loop of soft golden dust drifting upward (960x540 RGBA frames)."""
import math, os, random, sys
from PIL import Image, ImageDraw, ImageFilter

out = sys.argv[1]
os.makedirs(out, exist_ok=True)
W, H, FPS, T = 960, 540, 25, 24
N = T * FPS
random.seed(7)
parts = []
for _ in range(70):
    parts.append(dict(
        x=random.uniform(0, W), y=random.uniform(0, H),
        m=random.choice([1, 1, 2]),            # wraps per loop -> speed
        r=random.uniform(1.0, 3.2),
        a=random.uniform(.25, .8),
        sw=random.uniform(8, 30), sp=random.choice([1, 2, 3]), ph=random.uniform(0, 6.28),
        tw=random.choice([1, 2, 3]), tph=random.uniform(0, 6.28)))

for f in range(N):
    t = f / N  # 0..1 loop phase
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d, g = ImageDraw.Draw(im), ImageDraw.Draw(glow)
    for p in parts:
        y = (p["y"] - t * p["m"] * (H + 20)) % (H + 20) - 10
        x = p["x"] + p["sw"] * math.sin(2 * math.pi * p["sp"] * t + p["ph"])
        a = p["a"] * (0.6 + 0.4 * math.sin(2 * math.pi * p["tw"] * t + p["tph"]))
        r = p["r"]
        col = (255, 226, 160)
        g.ellipse([x - r * 3, y - r * 3, x + r * 3, y + r * 3], fill=col + (int(90 * a),))
        d.ellipse([x - r, y - r, x + r, y + r], fill=col + (int(255 * a),))
    glow = glow.filter(ImageFilter.GaussianBlur(4))
    Image.alpha_composite(glow, im).save(f"{out}/p{f:04d}.png")
print("frames", N)
