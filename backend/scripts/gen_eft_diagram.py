"""Generate a clean, self-contained EFT tapping-points diagram PNG.

Committed to backend/static/eft/default_tapping_points.png so the default never
depends on an external (hotlink-protected) site. Run once: python scripts/gen_eft_diagram.py
"""
from PIL import Image, ImageDraw, ImageFont
import os

W, H = 760, 560
BG = (248, 250, 252)
INK = (30, 41, 59)
ACCENT = (13, 148, 136)
DOTC = (220, 38, 38)
MUTED = (100, 116, 139)

img = Image.new("RGB", (W, H), BG)
d = ImageDraw.Draw(img)


def font(sz, bold=False):
    paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for p in paths:
        if os.path.exists(p):
            return ImageFont.truetype(p, sz)
    return ImageFont.load_default()


title_f = font(26, bold=True)
sub_f = font(14)
num_f = font(15, bold=True)
lbl_f = font(15)
loc_f = font(12)

# Title
d.text((30, 22), "EFT Tapping Points", font=title_f, fill=INK)
d.text((31, 56), "Tap gently 5–7 times on each point, in order.", font=sub_f, fill=MUTED)

# ── Simple front-facing figure on the left ──
cx = 230
# head
d.ellipse([cx - 55, 110, cx + 55, 220], outline=INK, width=3, fill=(255, 255, 255))
# neck
d.rectangle([cx - 16, 215, cx + 16, 245], outline=INK, width=3, fill=(255, 255, 255))
# torso (trapezoid via polygon)
d.polygon([(cx - 95, 250), (cx + 95, 250), (cx + 78, 470), (cx - 78, 470)],
          outline=INK, width=3, fill=(255, 255, 255))
# shoulders line
d.line([(cx - 95, 255), (cx + 95, 255)], fill=INK, width=2)

# Points on the figure: (number, x, y)
fig_pts = [
    (1, cx,        108),   # top of head
    (2, cx - 40,   150),   # eyebrow
    (3, cx - 62,   168),   # side of eye
    (4, cx - 40,   190),   # under eye
    (5, cx,        205),   # under nose
    (6, cx,        228),   # chin
    (7, cx - 55,   275),   # collarbone
    (8, cx - 92,   330),   # under arm
    (9, cx + 78,   300),   # karate chop (side of hand)
]
for n, x, y in fig_pts:
    d.ellipse([x - 11, y - 11, x + 11, y + 11], fill=DOTC, outline=(255, 255, 255), width=2)
    tw = d.textlength(str(n), font=num_f)
    d.text((x - tw / 2, y - 9), str(n), font=num_f, fill=(255, 255, 255))

# ── Legend on the right ──
legend = [
    (1, "Top of Head", "Crown of the head"),
    (2, "Eyebrow", "Start of the eyebrow"),
    (3, "Side of Eye", "Bone beside the eye"),
    (4, "Under Eye", "Bone under the eye"),
    (5, "Under Nose", "Between nose & lip"),
    (6, "Chin", "Crease under the lip"),
    (7, "Collarbone", "Just below the collarbone"),
    (8, "Under Arm", "~4 in. below the armpit"),
    (9, "Karate Chop", "Side of the hand (below pinky)"),
]
lx, ly = 380, 110
row_h = 44
for n, name, loc in legend:
    d.ellipse([lx, ly + 2, lx + 22, ly + 24], fill=ACCENT, outline=(255, 255, 255), width=2)
    tw = d.textlength(str(n), font=num_f)
    d.text((lx + 11 - tw / 2, ly + 4), str(n), font=num_f, fill=(255, 255, 255))
    d.text((lx + 34, ly), name, font=lbl_f, fill=INK)
    d.text((lx + 34, ly + 20), loc, font=loc_f, fill=MUTED)
    ly += row_h

d.text((31, H - 30), "JELCOS AI  ·  Emotional Gatekeeper", font=loc_f, fill=MUTED)

out = os.path.join(os.path.dirname(__file__), "..", "static", "eft", "default_tapping_points.png")
out = os.path.abspath(out)
img.save(out, "PNG")
print("wrote", out, os.path.getsize(out), "bytes")
