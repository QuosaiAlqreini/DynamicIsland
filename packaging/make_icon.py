"""Generate assets/icon.ico (the pill logo) with Pillow. Run: python packaging/make_icon.py"""
import os
from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def draw(size):
    s = size / 256
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([12 * s, 76 * s, 244 * s, 180 * s], radius=52 * s,
                        fill=(10, 11, 14, 255), outline=(0, 240, 255, 255), width=max(1, int(8 * s)))
    d.ellipse([40 * s, 100 * s, 96 * s, 156 * s], fill=(0, 240, 255, 255))
    d.rounded_rectangle([120 * s, 118 * s, 216 * s, 138 * s], radius=10 * s, fill=(248, 250, 252, 230))
    return img


if __name__ == "__main__":
    out = os.path.join(ROOT, "assets", "icon.ico")
    big = draw(256)
    big.save(out, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    big.save(os.path.join(ROOT, "assets", "icon.png"))
    print("wrote", out)
