"""Generate a few icon concepts for T Hub (256px previews)."""

from PIL import Image, ImageDraw
import math, os

OUT = r"D:\work\qd\assets"
os.makedirs(OUT, exist_ok=True)
S = 1024


def squircle(size, radius_ratio=0.22):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    r = int(size * radius_ratio)
    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=r, fill=None)
    return img, d, r


def arc(d, box, color, width, start=-90, end=250):
    d.arc(box, start=start, end=end, fill=color, width=width)


def mouse(d, cx, cy, w, h, color, width):
    # body
    d.rounded_rectangle([cx - w // 2, cy - h // 2, cx + w // 2, cy + h // 2],
                        radius=w // 2, outline=color, width=width)
    # wheel
    d.line([cx, cy - h // 2 + int(h * 0.12), cx, cy - h // 2 + int(h * 0.34)], fill=color, width=width)


def keyboard(d, cx, cy, w, h, color, width):
    d.rounded_rectangle([cx - w // 2, cy - h // 2, cx + w // 2, cy + h // 2],
                        radius=max(8, h // 5), outline=color, width=width)
    for i in range(3):
        y = cy - h // 4 + i * (h // 4)
        d.line([cx - w // 2 + int(w * 0.18), y, cx + w // 2 - int(w * 0.18), y], fill=color, width=max(4, width - 2))


def concept_a(path):
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    r = int(S * 0.24)
    d.rounded_rectangle([0, 0, S - 1, S - 1], radius=r, fill=(26, 27, 31, 255))
    box = [S * 0.19, S * 0.19, S * 0.81, S * 0.81]
    arc(d, box, (52, 199, 89, 255), int(S * 0.055), -90, 200)
    mouse(d, S // 2, S // 2, int(S * 0.30), int(S * 0.40), (245, 246, 248, 255), int(S * 0.035))
    img.resize((256, 256), Image.LANCZOS).save(path)


def concept_b(path):
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    r = int(S * 0.24)
    d.rounded_rectangle([0, 0, S - 1, S - 1], radius=r, fill=(250, 250, 252, 255))
    box = [S * 0.19, S * 0.19, S * 0.81, S * 0.81]
    arc(d, box, (52, 199, 89, 255), int(S * 0.055), -90, 200)
    mouse(d, S // 2, S // 2, int(S * 0.30), int(S * 0.40), (30, 31, 35, 255), int(S * 0.035))
    img.resize((256, 256), Image.LANCZOS).save(path)


def concept_c(path):
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    r = int(S * 0.24)
    d.rounded_rectangle([0, 0, S - 1, S - 1], radius=r, fill=(26, 27, 31, 255))
    # ring
    box = [S * 0.17, S * 0.17, S * 0.83, S * 0.83]
    arc(d, box, (52, 199, 89, 255), int(S * 0.06), -90, 190)
    # T monogram
    w = int(S * 0.075)
    d.line([S * 0.36, S * 0.40, S * 0.64, S * 0.40], fill=(245, 246, 248, 255), width=w)
    d.line([S * 0.50, S * 0.40, S * 0.50, S * 0.64], fill=(245, 246, 248, 255), width=w)
    img.resize((256, 256), Image.LANCZOS).save(path)


def concept_d(path):
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    r = int(S * 0.24)
    d.rounded_rectangle([0, 0, S - 1, S - 1], radius=r, fill=(26, 27, 31, 255))
    box = [S * 0.19, S * 0.19, S * 0.81, S * 0.81]
    arc(d, box, (52, 199, 89, 255), int(S * 0.055), -90, 200)
    keyboard(d, S // 2, S // 2, int(S * 0.44), int(S * 0.28), (245, 246, 248, 255), int(S * 0.035))
    img.resize((256, 256), Image.LANCZOS).save(path)


for name, fn in [("a-dark-mouse", concept_a), ("b-light-mouse", concept_b),
                 ("c-dark-T", concept_c), ("d-dark-keyboard", concept_d)]:
    fn(os.path.join(OUT, name + ".png"))

# contact sheet
sheet = Image.new("RGB", (4 * 276 + 20, 296), (240, 240, 244))
for i, name in enumerate(["a-dark-mouse", "b-light-mouse", "c-dark-T", "d-dark-keyboard"]):
    im = Image.open(os.path.join(OUT, name + ".png")).convert("RGBA")
    sheet.paste(im, (20 + i * 276, 20), im)
sheet.save(os.path.join(OUT, "icon-concepts.png"))
print("ok")
