"""A more realistic T Hub icon: shaded mouse + glowing battery ring on a squircle."""

from PIL import Image, ImageDraw, ImageFilter
import math, os

S = 1024
OUT = r"D:\work\qd\assets"
os.makedirs(OUT, exist_ok=True)


def linear_gradient(size, top, bottom):
    w, h = size
    img = Image.new("RGB", (1, h))
    d = ImageDraw.Draw(img)
    for y in range(h):
        t = y / max(1, h - 1)
        d.point((0, y), fill=tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3)))
    return img.resize((w, h), Image.BILINEAR)


def squircle_mask(size, radius):
    m = Image.new("L", (size, size), 0)
    d = ImageDraw.Draw(m)
    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=255)
    return m


def arc_ring(size, box, width, color, start=-90, end=200):
    layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.arc(box, start=start, end=end, fill=color + (255,), width=width)
    # round caps, on the stroke centerline (PIL draws the stroke inside the box)
    ib = [box[0] + width / 2, box[1] + width / 2, box[2] - width / 2, box[3] - width / 2]
    for ang in (start, end):
        cx = (ib[0] + ib[2]) / 2 + (ib[2] - ib[0]) / 2 * math.cos(math.radians(ang))
        cy = (ib[1] + ib[3]) / 2 + (ib[3] - ib[1]) / 2 * math.sin(math.radians(ang))
        r = width / 2
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color + (255,))
    return layer


def mouse_shape(w, h, radius):
    m = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(m)
    d.rounded_rectangle([0, 0, w - 1, h - 1], radius=radius, fill=255)
    return m


def build():
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    radius = int(S * 0.235)
    mask = squircle_mask(S, radius)

    # background: vertical gradient + subtle top sheen
    bg = linear_gradient((S, S), (44, 46, 52), (16, 17, 20)).convert("RGBA")
    img.paste(bg, (0, 0), mask)

    sheen = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    sd = ImageDraw.Draw(sheen)
    sd.ellipse([-S * 0.3, -S * 0.55, S * 1.3, S * 0.55], fill=(255, 255, 255, 26))
    sheen = sheen.filter(ImageFilter.GaussianBlur(60))
    img = Image.alpha_composite(img, Image.composite(sheen, Image.new("RGBA", (S, S), (0, 0, 0, 0)), mask))

    # subtle inner border
    border = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    bd = ImageDraw.Draw(border)
    bd.rounded_rectangle([2, 2, S - 3, S - 3], radius=radius, outline=(255, 255, 255, 46), width=3)
    img = Image.alpha_composite(img, border)

    # glowing battery ring
    box = [int(S * 0.175), int(S * 0.175), int(S * 0.825), int(S * 0.825)]
    ring = arc_ring(S, box, int(S * 0.062), (52, 199, 89))
    glow = ring.filter(ImageFilter.GaussianBlur(26))
    img = Image.alpha_composite(img, glow)
    img = Image.alpha_composite(img, ring)

    # mouse body
    w, h = int(S * 0.40), int(S * 0.53)
    mx, my = (S - w) // 2, (S - h) // 2 + int(S * 0.01)
    body_mask = mouse_shape(w, h, w // 2)
    body = linear_gradient((w, h), (250, 251, 253), (176, 180, 188)).convert("RGBA")

    # side shading
    shade = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    shd = ImageDraw.Draw(shade)
    shd.ellipse([-w * 0.5, -h * 0.2, w * 1.15, h * 1.3], fill=(0, 0, 0, 0))
    shd.rectangle([0, 0, int(w * 0.16), h], fill=(0, 0, 0, 26))
    shd.rectangle([int(w * 0.84), 0, w, h], fill=(0, 0, 0, 34))
    body = Image.alpha_composite(body, shade.filter(ImageFilter.GaussianBlur(8)))

    # top highlight
    hi = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    hid = ImageDraw.Draw(hi)
    hid.ellipse([w * 0.16, h * 0.05, w * 0.84, h * 0.42], fill=(255, 255, 255, 90))
    hi = hi.filter(ImageFilter.GaussianBlur(18))
    body = Image.alpha_composite(body, Image.composite(hi, Image.new("RGBA", (w, h), (0, 0, 0, 0)), body_mask))

    # edge
    edge = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ed = ImageDraw.Draw(edge)
    ed.rounded_rectangle([0, 0, w - 1, h - 1], radius=w // 2, outline=(90, 94, 102, 110), width=4)
    body = Image.alpha_composite(body, edge)

    # wheel slot + wheel
    slot = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    sld = ImageDraw.Draw(slot)
    sld.rounded_rectangle([w * 0.44, h * 0.10, w * 0.56, h * 0.36], radius=int(w * 0.06), fill=(60, 63, 70, 200))
    slot = slot.filter(ImageFilter.GaussianBlur(3))
    body = Image.alpha_composite(body, Image.composite(slot, Image.new("RGBA", (w, h), (0, 0, 0, 0)), body_mask))

    wheel = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    wd = ImageDraw.Draw(wheel)
    wd.rounded_rectangle([w * 0.455, h * 0.13, w * 0.545, h * 0.31], radius=int(w * 0.045),
                         fill=(120, 124, 132, 255))
    wheel = wheel.filter(ImageFilter.GaussianBlur(1))
    body = Image.alpha_composite(body, Image.composite(wheel, Image.new("RGBA", (w, h), (0, 0, 0, 0)), body_mask))

    # soft drop shadow behind the mouse
    shadow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    shd2 = ImageDraw.Draw(shadow)
    shd2.ellipse([mx - w * 0.1, my + h * 0.55, mx + w * 1.1, my + h * 1.05], fill=(0, 0, 0, 120))
    shadow = shadow.filter(ImageFilter.GaussianBlur(30))
    img = Image.alpha_composite(img, Image.composite(shadow, Image.new("RGBA", (S, S), (0, 0, 0, 0)), mask))

    body_img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    body_img.paste(body, (mx, my), body_mask)
    img = Image.alpha_composite(img, body_img)

    return img


icon = build()
icon.save(os.path.join(OUT, "realistic-master.png"))
for size in (256, 128, 64, 48, 32, 24, 16):
    icon.resize((size, size), Image.LANCZOS).save(os.path.join(OUT, f"realistic-{size}.png"))

# preview: dark and light backgrounds
prev = Image.new("RGB", (620, 320), (238, 239, 243))
dark = Image.new("RGB", (280, 280), (24, 25, 29))
prev.paste(dark, (20, 20))
small_dark = icon.resize((240, 240), Image.LANCZOS)
prev.paste(small_dark, (40, 40), small_dark)
light = Image.new("RGB", (280, 280), (250, 250, 252))
prev.paste(light, (320, 20))
prev.paste(small_dark, (340, 40), small_dark)
# size strip
x = 40
for s in (64, 48, 32, 24, 16):
    im = icon.resize((s, s), Image.LANCZOS)
    prev.paste(im, (x, 250), im)
    x += s + 16
prev.save(os.path.join(OUT, "realistic-preview.png"))
print("ok")
