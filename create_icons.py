from PIL import Image, ImageDraw
import os

OUT = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(OUT, exist_ok=True)

TEAL_DARK  = "#1A9B95"
TEAL_MID   = "#22B5AE"
TEAL_LIGHT = "#2ECFC7"
WHITE      = "#FFFFFF"
OFF_WHITE  = "#E8F8F7"

def make_icon(size):
    img  = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # ── Background circle ──
    draw.ellipse([0, 0, size-1, size-1], fill=TEAL_MID)
    # Inner highlight for depth
    hl = int(size * 0.06)
    draw.ellipse([hl, hl, size-hl-1, size-hl-1], fill=TEAL_LIGHT)

    cx = size // 2
    cy = size // 2

    # ── Pot body ──
    pw = int(size * 0.50)   # pot width
    ph = int(size * 0.36)   # pot height
    px = cx - pw // 2
    py = cy - ph // 2 + int(size * 0.07)  # shift down slightly

    # Pot body (rounded bottom, straight sides)
    draw.rounded_rectangle(
        [px, py, px + pw, py + ph],
        radius=int(ph * 0.30),
        fill=WHITE
    )

    # ── Pot rim (slightly wider than body) ──
    rim_h  = int(size * 0.06)
    rim_ov = int(size * 0.03)   # overhang each side
    draw.rounded_rectangle(
        [px - rim_ov, py - rim_h, px + pw + rim_ov, py + int(rim_h * 0.4)],
        radius=int(rim_h * 0.4),
        fill=WHITE
    )

    # ── Lid ──
    lid_h  = int(size * 0.07)
    lid_ov = int(size * 0.02)
    draw.rounded_rectangle(
        [px - lid_ov, py - rim_h - lid_h, px + pw + lid_ov, py - rim_h + int(lid_h * 0.3)],
        radius=int(lid_h * 0.45),
        fill=OFF_WHITE
    )

    # Lid knob
    knob_w = int(size * 0.10)
    knob_h = int(size * 0.05)
    kx = cx - knob_w // 2
    ky = py - rim_h - lid_h - knob_h + int(size * 0.01)
    draw.rounded_rectangle(
        [kx, ky, kx + knob_w, ky + knob_h],
        radius=int(knob_h * 0.5),
        fill=WHITE
    )

    # ── Handles ──
    handle_w = int(size * 0.08)
    handle_h = int(size * 0.14)
    handle_y = py + int(ph * 0.15)

    # Left handle
    draw.rounded_rectangle(
        [px - handle_w - int(size*0.01), handle_y,
         px + int(size*0.01),            handle_y + handle_h],
        radius=int(handle_w * 0.4),
        fill=WHITE
    )
    # Right handle
    draw.rounded_rectangle(
        [px + pw - int(size*0.01), handle_y,
         px + pw + handle_w + int(size*0.01), handle_y + handle_h],
        radius=int(handle_w * 0.4),
        fill=WHITE
    )

    # ── Steam lines above lid ──
    steam_top_y = ky - int(size * 0.03)
    steam_len   = int(size * 0.11)
    sw = max(int(size * 0.025), 2)

    for i, offset in enumerate([-int(size*0.10), 0, int(size*0.10)]):
        sx     = cx + offset
        sy_bot = steam_top_y
        sy_top = sy_bot - steam_len
        wave   = int(size * 0.035) * (1 if i % 2 == 0 else -1)
        mid_y  = (sy_bot + sy_top) // 2
        draw.line(
            [(sx, sy_bot), (sx + wave, mid_y), (sx, sy_top)],
            fill=(255, 255, 255, 200),
            width=sw
        )

    return img

for sz in [192, 512]:
    path = os.path.join(OUT, f"icon-{sz}.png")
    make_icon(sz).save(path)
    print(f"נוצר: icon-{sz}.png")
