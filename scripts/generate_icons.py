"""
generate_icons.py
Generates all 3 floating-widget icon states programmatically using Pillow.
Run with: .\.venv\Scripts\python.exe scripts\generate_icons.py
"""

import math
import os
from PIL import Image, ImageDraw, ImageFilter

SIZE   = 256      # canvas size
HALF   = SIZE // 2
RADIUS = HALF - 4 # outer circle radius (leaves 4px transparent padding)

# Resolve paths relative to script location
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DIR    = os.path.join(SCRIPT_DIR, "..", "assets", "icons")

# -- Colour palettes per state -------------------------------------------------
STATES = {
    "mic_idle": {
        "grad_inner": (55, 120, 230),   # bright blue
        "grad_outer": (20,  60, 160),   # deep navy
        "glow":       (80, 160, 255),
    },
    "mic_active": {
        "grad_inner": (230,  60,  70),  # bright crimson
        "grad_outer": (140,  20,  30),  # deep red
        "glow":       (255,  90, 100),
    },
    "mic_loading": {
        "grad_inner": (245, 160,  30),  # amber
        "grad_outer": (180,  90,  10),  # deep orange
        "glow":       (255, 200,  80),
    },
}


# -- Helpers -------------------------------------------------------------------

def lerp_colour(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def make_radial_gradient(size, inner_rgb, outer_rgb):
    """Build a radial gradient image (RGBA) from centre outward."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    cx = cy = size / 2
    max_r = size / 2
    pixels = img.load()
    for y in range(size):
        for x in range(size):
            dist = math.hypot(x - cx, y - cy)
            t = min(dist / max_r, 1.0)
            t = t ** 0.7
            colour = lerp_colour(inner_rgb, outer_rgb, t)
            pixels[x, y] = (*colour, 255)
    return img


def make_circle_mask(size, radius, feather=1):
    """Create an anti-aliased circular alpha mask."""
    # Draw at 2x then downsample for smooth edges without a wide feather fringe
    scale  = 2
    ss     = size * scale
    ss_r   = radius * scale
    mask_ss = Image.new("L", (ss, ss), 0)
    draw    = ImageDraw.Draw(mask_ss)
    cx = cy = ss // 2
    draw.ellipse([cx - ss_r, cy - ss_r, cx + ss_r, cy + ss_r], fill=255)
    mask = mask_ss.resize((size, size), Image.Resampling.LANCZOS)
    return mask


def draw_glow_ring(draw, cx, cy, radius, glow_rgb, alpha=80, width=18):
    """Draw a soft luminous ring just inside the edge."""
    for i in range(width, 0, -1):
        a = int(alpha * (i / width) ** 2)
        r = radius - (width - i)
        colour = (*glow_rgb, a)
        draw.ellipse(
            [cx - r, cy - r, cx + r, cy + r],
            outline=colour,
            width=1,
        )


def draw_gloss_arc(draw, cx, cy, radius, bg_rgb):
    """Small glossy highlight arc in the top-left quadrant."""
    hr = int(radius * 0.70)
    light = tuple(min(255, c + 90) for c in bg_rgb)
    draw.arc(
        [cx - hr, cy - int(hr * 1.1), cx + int(hr * 0.6), cy],
        start=35, end=145,
        fill=(*light, 60),
        width=max(2, SIZE // 50),
    )


def draw_microphone(draw, cx, cy, size, colour=(255, 255, 255)):
    """Draw a modern, clean microphone icon centred at (cx, cy)."""
    lw = max(2, size // 40)

    bw   = int(size * 0.130)
    bh   = int(size * 0.200)
    btop = cy - int(size * 0.175)

    # Capsule body
    draw.rectangle([cx - bw, btop + bw, cx + bw, btop + bh], fill=colour)
    draw.ellipse([cx - bw, btop, cx + bw, btop + bw * 2], fill=colour)
    draw.ellipse([cx - bw, btop + bh - bw * 2, cx + bw, btop + bh], fill=colour)

    # Stand arc
    arc_r  = int(size * 0.180)
    arc_cy = btop + bh
    draw.arc(
        [cx - arc_r, arc_cy - arc_r, cx + arc_r, arc_cy + arc_r],
        start=0, end=180, fill=colour, width=lw + 1,
    )

    # Stem
    stem_top = arc_cy
    stem_bot = cy + int(size * 0.230)
    draw.line([cx, stem_top, cx, stem_bot], fill=colour, width=lw + 1)

    # Base bar
    base_hw = int(size * 0.110)
    draw.line([cx - base_hw, stem_bot, cx + base_hw, stem_bot], fill=colour, width=lw + 1)


def draw_sound_waves(draw, cx, cy, size, colour=(255, 255, 255)):
    """Three arcs on each side of the mic (for active/recording state)."""
    radii  = [int(size * 0.260), int(size * 0.320), int(size * 0.380)]
    alphas = [180, 120, 60]
    for r, a in zip(radii, alphas):
        c = (*colour, a)
        draw.arc([cx - r, cy - r, cx + r, cy + r], start=145, end=215,
                 fill=c, width=max(2, size // 60))
        draw.arc([cx - r, cy - r, cx + r, cy + r], start=-35, end=35,
                 fill=c, width=max(2, size // 60))


def draw_spinner_dots(draw, cx, cy, size, colour=(255, 255, 255)):
    """Eight dots arranged in a circle (loading indicator)."""
    dot_r  = max(3, size // 38)
    ring_r = int(size * 0.300)
    for i in range(8):
        angle = math.radians(i * 45)
        dx    = cx + int(ring_r * math.sin(angle))
        dy    = cy - int(ring_r * math.cos(angle))
        alpha = int(255 * (i + 1) / 8)
        draw.ellipse([dx - dot_r, dy - dot_r, dx + dot_r, dy + dot_r],
                     fill=(*colour, alpha))


# -- Main builder --------------------------------------------------------------

def build_icon(name, palette, with_waves=False, with_spinner=False):
    scale = 4
    ss    = SIZE * scale
    ss_r  = RADIUS * scale

    base = make_radial_gradient(ss, palette["grad_inner"], palette["grad_outer"])
    mask = make_circle_mask(ss, ss_r, feather=scale)
    base.putalpha(mask)

    overlay = Image.new("RGBA", (ss, ss), (0, 0, 0, 0))
    draw    = ImageDraw.Draw(overlay, "RGBA")
    ss_cx   = ss_cy = ss // 2

    draw_glow_ring(draw, ss_cx, ss_cy, ss_r, palette["glow"], alpha=90, width=ss // 16)
    draw_gloss_arc(draw, ss_cx, ss_cy, ss_r, palette["grad_inner"])

    if with_waves:
        draw_sound_waves(draw, ss_cx, ss_cy, ss, colour=(255, 255, 255))
    if with_spinner:
        draw_spinner_dots(draw, ss_cx, ss_cy, ss, colour=(255, 255, 255))

    draw_microphone(draw, ss_cx, ss_cy, ss, colour=(255, 255, 255))

    combined = Image.alpha_composite(base, overlay)
    final    = combined.resize((SIZE, SIZE), Image.Resampling.LANCZOS)

    out_path = os.path.join(OUT_DIR, f"{name}.png")
    final.save(out_path, "PNG")
    print(f"  OK  Saved  {out_path}")


if __name__ == "__main__":
    os.makedirs(OUT_DIR, exist_ok=True)
    print("Generating icons...")
    build_icon("mic_idle",    STATES["mic_idle"])
    build_icon("mic_active",  STATES["mic_active"],  with_waves=True)
    build_icon("mic_loading", STATES["mic_loading"], with_spinner=True)
    print("Done.")
