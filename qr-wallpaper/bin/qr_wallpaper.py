#!/usr/bin/env python3
"""
qr_wallpaper.py -- Cross-stitch QR wallpaper maker.

Overlays a QR code on a background image as a phone wallpaper:
  1. extracts the QR module matrix verbatim from the QR image (never re-encodes),
  2. redraws data modules as "+" cross-stitch strokes, keeps finder patterns solid,
  3. samples stroke + panel colors from the background palette,
  4. places the panel in the least-busy region of the background,
  5. decode-verifies the result with OpenCV when available.

Usage:
    python3 qr_wallpaper.py --background bg.jpg --qr qr.png --output out.png
                            [--qr-width 0.22] [--stroke 192B11] [--panel EEF5EC]
                            [--position auto|x,y] [--verify/--no-verify]
"""

import argparse
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter


# ---------------------------------------------------------------- QR matrix
def extract_matrix(qr_img):
    """Return (matrix, n): n x n bool array sampled from the QR image."""
    g = np.asarray(qr_img.convert("L"))
    t = g < 128
    if t.mean() > 0.5:  # tolerate inverted input
        t = ~t
    ys = np.where(t.any(axis=1))[0]
    xs = np.where(t.any(axis=0))[0]
    if len(ys) == 0 or len(xs) == 0:
        raise ValueError("no QR code found: image is blank")
    y0, y1 = ys[0], ys[-1]
    x0, x1 = xs[0], xs[-1]
    Wc = x1 - x0 + 1

    def sample(n, i, j):
        s = Wc / n
        cx = int(x0 + (j + 0.5) * s)
        cy = int(y0 + (i + 0.5) * s)
        return t[max(0, cy - 1):cy + 2, max(0, cx - 1):cx + 2].mean() > 0.5

    def finder_ok(n):
        for k in range(7):
            if not sample(n, 0, k) or not sample(n, 6, k):
                return False
            if not sample(n, k, 0) or not sample(n, k, 6):
                return False
        for i in range(1, 6):
            for j in range(1, 6):
                if sample(n, i, j) != (2 <= i <= 4 and 2 <= j <= 4):
                    return False
        return sample(n, 0, n - 1) and sample(n, n - 1, 0)

    n = None
    for v in range(21, 178, 4):
        if abs(Wc / v - round(Wc / v)) < 0.06 and finder_ok(v):
            n = v
            break
    if n is None:
        raise ValueError("could not detect QR version / finder patterns")
    M = np.array([[sample(n, i, j) for j in range(n)] for i in range(n)])
    return M, n


# ---------------------------------------------------------------- palette
def sample_palette(bg_rgb):
    """(stroke_color, panel_tint) measured from the background image.

    Stroke: deep tone from the darkest saturated pixels. Tint: near-white with a
    perceptible hint of the image's dominant hue (sampled image-wide, so a pale
    placement region can't wash it out).
    """
    a = np.asarray(bg_rgb).astype(int)
    mx, mn = a.max(-1), a.min(-1)
    sat = mx - mn
    m = sat > 25
    if m.sum() > 500:
        colored = a[m].reshape(-1, 3)
        hue_ref = np.median(colored, axis=0)
    else:
        colored = a.reshape(-1, 3)
        hue_ref = np.array([245.0, 245.0, 245.0])
    lum = colored.mean(1)
    dark = colored[lum < np.percentile(lum, 15)]
    stroke = np.median(dark, axis=0).astype(float)
    if stroke.mean() > 90:  # ensure a deep tone
        stroke *= 90.0 / stroke.mean()
    tint = np.round(255 * 0.90 + hue_ref * 0.10).clip(230, 255)
    return tuple(int(v) for v in stroke), tuple(int(v) for v in tint)


# ---------------------------------------------------------------- placement
def find_placement(bg_gray, P):
    """Least-busy P x P region (integral-image box means over edge magnitude)."""
    Hh, Ww = bg_gray.shape
    gy, gx = np.gradient(bg_gray.astype(float))
    mag = np.hypot(gx, gy)
    dark = (bg_gray < 100).astype(float)  # text / dark subjects
    ii = np.zeros((Hh + 1, Ww + 1))
    ii[1:, 1:] = np.cumsum(np.cumsum(mag, axis=0), axis=1)
    jj = np.zeros((Hh + 1, Ww + 1))
    jj[1:, 1:] = np.cumsum(np.cumsum(dark, axis=0), axis=1)

    def box_mean(x0, y0):
        x1, y1 = x0 + P, y0 + P
        return (ii[y1, x1] - ii[y0, x1] - ii[y1, x0] + ii[y0, x0]) / (P * P)

    def dark_frac(x0, y0):
        x1, y1 = x0 + P, y0 + P
        return (jj[y1, x1] - jj[y0, x1] - jj[y1, x0] + jj[y0, x0]) / (P * P)

    m = int(0.03 * min(Hh, Ww))
    step = max(16, P // 4)

    def search(min_gap):
        best = None
        for y in range(m, Hh - P - m + 1, step):
            for x in range(m, Ww - P - m + 1, step):
                if min(x, y, Ww - x - P, Hh - y - P) < min_gap:
                    continue
                key = (round(box_mean(x, y) + 8 * dark_frac(x, y), 1),  # bucketed
                       abs((y + P / 2) - Hh / 2) / Hh
                       + abs((x + P / 2) - Ww / 2) / Ww)
                if best is None or key < best[0]:
                    best = (key, (x, y, P))
        return best

    inner = search(0.08 * min(Hh, Ww))  # prefer clear of edges
    outer = search(0)                   # fallback: anywhere
    if inner is None:
        best = outer
    elif outer is None or inner[0][0] <= max(2.5 * outer[0][0], outer[0][0] + 1e-6):
        best = inner
    else:  # image is busy everywhere: take the truly emptiest spot
        best = outer
    if best is None:
        raise ValueError("background too small for the QR panel")
    return best[1]


# ---------------------------------------------------------------- render
def render_panel(M, n, q, stroke, tint):
    """Cross-stitch QR on a tinted square panel. Returns RGBA panel image."""
    cell = q / n
    img = Image.new("RGBA", (q, q), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    fg = stroke + (255,)

    def in_finder(i, j):
        return (i < 7 and j < 7) or (i < 7 and j >= n - 7) or (i >= n - 7 and j < 7)

    lw = max(2, int(cell * 0.24))
    r = cell * 0.34
    for i in range(n):
        for j in range(n):
            if not M[i, j]:
                continue
            x, y = j * cell, i * cell
            if in_finder(i, j):
                d.rectangle([x, y, x + cell - 0.5, y + cell - 0.5], fill=fg)
            else:
                cx, cy = x + cell / 2, y + cell / 2
                d.line([(cx - r, cy), (cx + r, cy)], fill=fg, width=lw)
                d.line([(cx, cy - r), (cx, cy + r)], fill=fg, width=lw)

    quiet = int(q * 0.115)
    ppad = int(q * 0.09)
    pw = ph = q + 2 * (quiet + ppad)
    pmask = Image.new("L", (pw, ph), 0)
    ImageDraw.Draw(pmask).rounded_rectangle(
        [0, 0, pw - 1, ph - 1], radius=int(pw * 0.09), fill=255)
    pmask = pmask.filter(ImageFilter.GaussianBlur(2))
    panel = Image.new("RGBA", (pw, ph), tint + (255,))
    panel.putalpha(pmask)
    panel.alpha_composite(img, (quiet + ppad, quiet + ppad))
    return panel, pmask


# ---------------------------------------------------------------- verify
def verify_decode(qr_path, final_img, box):
    """Decode original QR and final panel crop; return (match|None, d0, d1)."""
    try:
        import cv2
    except ImportError:
        return None, "", ""
    det = cv2.QRCodeDetector()
    d0, _, _ = det.detectAndDecode(cv2.imread(qr_path))
    x, y, P = box
    crop = np.asarray(final_img)[y:y + P, x:x + P]
    d1, _, _ = det.detectAndDecode(crop)
    return (bool(d0) and d0 == d1), d0, d1


def hex_color(s):
    s = s.lstrip("#")
    return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--background", required=True)
    ap.add_argument("--qr", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--qr-width", type=float, default=0.22,
                    help="QR module-area width as fraction of background width")
    ap.add_argument("--stroke", default=None, help="override stroke color, hex e.g. 192B11")
    ap.add_argument("--panel", default=None, help="override panel tint, hex e.g. EEF5EC")
    ap.add_argument("--position", default="auto",
                    help='"auto" or "x,y" top-left of the panel')
    ap.add_argument("--verify", dest="verify", action="store_true", default=True)
    ap.add_argument("--no-verify", dest="verify", action="store_false")
    ap.add_argument("--shadow", dest="shadow", action="store_true", default=True)
    ap.add_argument("--no-shadow", dest="shadow", action="store_false")
    a = ap.parse_args()

    bg = Image.open(a.background).convert("RGB")
    W, H = bg.size
    M, n = extract_matrix(Image.open(a.qr).convert("RGB"))
    print(f"QR modules: {n}x{n}", flush=True)

    q = int(W * a.qr_width)
    stroke = hex_color(a.stroke) if a.stroke else None
    tint = hex_color(a.panel) if a.panel else None

    # provisional placement for palette sampling (refined after render)
    quiet = int(q * 0.115)
    ppad = int(q * 0.09)
    P = q + 2 * (quiet + ppad)
    if a.position == "auto":
        box = find_placement(np.asarray(bg.convert("L")), P)
    else:
        x, y = (int(v) for v in a.position.split(","))
        box = (x, y, P)
    if stroke is None or tint is None:
        s_auto, t_auto = sample_palette(bg)
        stroke = stroke or s_auto
        tint = tint or t_auto
    print(f"stroke: #{stroke[0]:02X}{stroke[1]:02X}{stroke[2]:02X} "
          f"panel: #{tint[0]:02X}{tint[1]:02X}{tint[2]:02X}", flush=True)

    panel, pmask = render_panel(M, n, q, stroke, tint)

    x, y, _ = box
    base = bg.convert("RGBA")
    if a.shadow:
        sm = pmask.filter(ImageFilter.GaussianBlur(14)).point(lambda v: int(v * 0.30))
        shadow = Image.new("RGBA", (P, P), (60, 70, 70, 255))
        shadow.putalpha(sm)
        base.alpha_composite(shadow, (x, y + 14))
    base.alpha_composite(panel, (x, y))
    final = base.convert("RGB")
    final.save(a.output, quality=95)
    print(f"panel at {(x, y)} size {P} -> {a.output}", flush=True)

    if a.verify:
        match, d0, d1 = verify_decode(a.qr, final, box)
        print(f"DECODE-MATCH: {match} (orig={d0[:40]!r})", flush=True)
        if match is False:
            sys.exit(2)
    else:
        print("DECODE-MATCH: SKIPPED (--no-verify)", flush=True)


if __name__ == "__main__":
    main()
