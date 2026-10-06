---
name: "qr_wallpaper"
description: "Overlay a QR code on a background image as a phone wallpaper: cross-stitch-styled QR ('+' strokes, solid finders) on a palette-matched square panel, decode-verified scannable. Use when the user wants a decorative/styled QR wallpaper — e.g. '把二维码做到壁纸上', '十字绣二维码', 'QR wallpaper'."
---

# QR Wallpaper

## Purpose
Turn any background image + any QR code image into a phone wallpaper: the QR is redrawn
cross-stitch style ("+" strokes for data modules, solid finder patterns), colored from the
background's measured palette, placed in a quiet region, and decode-verified.

## Tooling
Helper: `~/workspace/skills/qr-wallpaper/bin/qr_wallpaper.py` (needs Python 3, PIL, numpy;
verification needs `opencv-python-headless`).

```bash
python3 ~/workspace/skills/qr-wallpaper/bin/qr_wallpaper.py \
  --background <bg.jpg> --qr <qr.png> --output <out.png> \
  [--qr-width 0.22] [--stroke 192B11] [--panel EEF5EC] \
  [--position auto|x,y] [--no-shadow] [--no-verify]
```

- `--qr-width`: QR module-area width as a fraction of background width (default 0.22).
- `--position auto`: picks the least-busy region via edge-density search; or pass `x,y`
  (panel top-left) for manual placement.
- `--stroke` / `--panel`: hex overrides; default is palette-sampled from the background.
- Prints QR module count, sampled colors, panel box, and `DECODE-MATCH: True/False/SKIPPED`.

## Workflow
1. Confirm the two inputs: a background image and a QR code image. Ask if either is ambiguous.
2. Run the helper, writing `--output` under `~/workspace/your_files/` (user-visible deliverable).
3. Open the output image and eyeball placement and aesthetics; if auto placement lands on
   text or a subject, re-run with a manual `--position x,y`.
4. Check the `DECODE-MATCH` line:
   - `True` → deliver, state that scanning was verified.
   - `False` → do not deliver as "guaranteed"; adjust (e.g. larger `--qr-width`) and retry.
   - `SKIPPED` → deliver but say plainly it was not machine-verified and ask the user to
     scan it with their phone.
5. Attach the final PNG; mention the sampled stroke/panel colors briefly.

## Output Contract
- Final wallpaper PNG at the background's original resolution.
- Tinted square panel (slightly rounded corners), no border, no tail, subtle shadow.
- Green/"+" cross-stitch QR with solid finder patterns and an intact quiet zone.
- Decode-verification result stated in the reply.

## Operating Rules
1. Never re-encode the QR data — the helper samples the original module matrix verbatim.
2. Colors are measured from the background unless the user overrides them; never invent
   palette colors.
3. Keep the quiet zone intact: nothing may be drawn in the panel margin around the QR.
4. Finder patterns stay solid; only data modules get the "+" treatment.
