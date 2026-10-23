"""Draw the static bar images.
"""
from __future__ import annotations

import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .messages import text as _msg

PALETTE = [
    "#0072b2", "#d55e00", "#009e73", "#cc79a7", "#e69f00",
    "#56b4e9", "#f0e442", "#332288", "#88ccee", "#44aa99",
    "#117733", "#999933", "#ddcc77", "#cc6677", "#882255",
    "#aa4499", "#661100", "#6699cc", "#888888", "#8d6e63",
]


FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/Library/Fonts/Arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
]


def hex_rgb(h):
    h = h.lstrip("#")
    return np.array([int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)], dtype=np.uint8)


def hsv_hex(i):
    """Extra colours once PALETTE is used up. Golden-angle hue, s=0.65, v=0.90."""
    hue = (i * 137.508) % 360.0
    s, v = 0.65, 0.90
    c = v * s
    x = c * (1 - abs((hue / 60.0) % 2 - 1))
    m = v - c
    hi = int(hue // 60) % 6
    rgb = [
        (c, x, 0), (x, c, 0), (0, c, x),
        (0, x, c), (x, 0, c), (c, 0, x),
    ][hi]
    vals = [int(round((t + m) * 255)) for t in rgb]
    return "#%02x%02x%02x" % tuple(vals)


def next_free(used, start):
    i = start
    while True:
        if i < len(PALETTE):
            h = PALETTE[i]
        else:
            h = hsv_hex(i)
        if h.lower() not in used:
            return h.lower()
        i += 1


def assign_colors(k, owners, group_color, col_color, *, language="en"):
    hexes = [None] * k
    used = set()
    for c in range(k):
        if (c + 1) in col_color:
            hx = col_color[c + 1]
            if hx in used:
                hx = next_free(used, c)
            hexes[c] = hx
            used.add(hx)
    for c, ow in enumerate(owners):
        if hexes[c] is not None:
            continue
        for g, _iid, _q in ow:
            if g in group_color and group_color[g] not in used:
                hexes[c] = group_color[g]
                used.add(hexes[c])
                break
    for c in range(k):
        if hexes[c] is None:
            hx = next_free(used, c)
            hexes[c] = hx
            used.add(hx)
    if len(set(hexes)) != k:
        raise SystemExit(_msg("duplicate_color", language, k=k))
    return hexes


def ancestry_image(q, hexes, height):
    """One pixel column per sample. Column 0 of q is the bottom of the bar."""
    n, k = q.shape
    rgb = np.full((height, n, 3), 255, dtype=np.uint8)
    cols = [hex_rgb(h) for h in hexes]
    for i in range(n):
        bounds = np.cumsum(q[i])
        for y in range(height):
            t = (height - 1 - y) / float(height)
            c = int(np.searchsorted(bounds, t + 1e-12, side="right"))
            if c >= k:
                continue
            rgb[y, i] = cols[c]
    return rgb


def load_font(size):
    for path in FONT_CANDIDATES:
        if os.path.isfile(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def text_wh(font, text):
    box = font.getbbox(text)
    return box[2] - box[0], box[3] - box[1]


def draw_rotated(base, x, y, text, font, fill):
    w, h = text_wh(font, text)
    tmp = Image.new("RGBA", (w + 4, h + 4), (0, 0, 0, 0))
    ImageDraw.Draw(tmp).text((1, 0), text, font=font, fill=fill)
    rot = tmp.rotate(45, expand=True, resample=Image.Resampling.BICUBIC)
    base.paste(rot, (int(x), int(y)), rot)
    return rot.size


def render(path, rows, spans, bar_w, bar_h, title, *, language="en"):
    """rows: list of {k, image(ndarray HxN), legend[(hex, text)]} in K order."""
    font = load_font(15)
    font_s = load_font(13)
    font_k = load_font(16)
    title_font = load_font(18)
    ink = (31, 41, 55, 255)
    left = 56
    gap = 12
    leg_w = 0
    for row in rows:
        for _hx, text in row["legend"]:
            leg_w = max(leg_w, text_wh(font_s, text)[0] + 22)
    leg_w = min(max(leg_w, 80), 420)
    names = [s["name"] for s in spans]
    longest = max([text_wh(font, s)[0] for s in names], default=0)
    rotate = len(spans) > 12 or (spans and bar_w / len(spans) < longest + 8)
    if rotate:
        label_h = int(longest * 0.75) + 28
    else:
        label_h = text_wh(font, "Ag")[1] + 16
    title_h = 32 if title else 8
    n_row = len(rows)
    row_pitch = []
    for row in rows:
        need = 4 + len(row["legend"]) * 18
        row_pitch.append(max(bar_h, need))
    width = left + bar_w + gap + leg_w + 16
    height = title_h + sum(row_pitch) + label_h + 12
    canvas = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(canvas)
    if title:
        draw.text((left, 6), title, font=title_font, fill=(31, 41, 55))
    y = title_h
    n = rows[0]["image"].shape[1]
    for row, pitch in zip(rows, row_pitch):
        img = Image.fromarray(row["image"])
        img = img.resize((bar_w, bar_h), Image.Resampling.NEAREST)
        bar_y = y + (pitch - bar_h) // 2
        canvas.paste(img, (left, bar_y))
        draw.text((8, bar_y + bar_h // 2 - 8), "K%d" % row["k"], font=font_k, fill=(31, 41, 55))
        lx = left + bar_w + gap
        ly = y + 2
        for hx, text in row["legend"]:
            draw.rectangle([lx, ly + 2, lx + 12, ly + 14], fill=hx)
            draw.text((lx + 16, ly), text, font=font_s, fill=(31, 41, 55))
            ly += 18
        y += pitch
    # group boundaries and names, shared x
    boundary = (148, 163, 184)
    for span in spans:
        if span["start"] <= 0:
            continue
        x = left + int(span["start"] * bar_w / n)
        draw.line([(x, title_h), (x, title_h + sum(row_pitch))], fill=boundary, width=1)
    y_lab = title_h + sum(row_pitch) + 4
    for span in spans:
        px0 = left + int(span["start"] * bar_w / n)
        px1 = left + int(span["end"] * bar_w / n)
        if px1 - px0 < 14:
            print(_msg("narrow_group", language, name=span["name"]), file=sys.stderr)
            continue
        mid = (px0 + px1) // 2
        if rotate:
            draw_rotated(canvas, mid - 6, y_lab, span["name"], font_s, ink)
        else:
            tw, _th = text_wh(font, span["name"])
            draw.text((mid - tw // 2, y_lab), span["name"], font=font, fill=(31, 41, 55))
    folder = os.path.dirname(os.path.abspath(path))
    if folder:
        os.makedirs(folder, exist_ok=True)
    canvas.save(path, dpi=(150, 150))
    if path.lower().endswith(".png"):
        canvas.save(os.path.splitext(path)[0] + ".pdf", "PDF", resolution=150.0)


def cv_k_marks(rows):
    """Per-K min, max, median, and numeric-row count.

    Rows with ``cv_error`` ``NA`` are skipped. K values are the distinct
    integers, sorted. The median is ``numpy.median``.
    """
    buckets = {}
    for row in rows:
        cv = row["cv_error"]
        k_text = str(row["k"])
        if cv == "NA" or not k_text.isdigit():
            continue
        buckets.setdefault(int(k_text), []).append(float(cv))
    marks = []
    for k in sorted(buckets):
        vals = np.asarray(buckets[k], dtype=float)
        marks.append({
            "k": k,
            "median": float(np.median(vals)),
            "vmin": float(vals.min()),
            "vmax": float(vals.max()),
            "n": int(vals.size),
        })
    return marks


def _ascii_tick(value):
    return "%.4g" % value


def _paste_up(base, text, font, fill, cx, cy):
    """Draw ASCII text rotated so it reads upward, centered at cx, cy."""
    width, height = text_wh(font, text)
    tmp = Image.new("RGBA", (width + 2, height + 2), (0, 0, 0, 0))
    ImageDraw.Draw(tmp).text((1, 0), text, font=font, fill=fill)
    rot = tmp.rotate(90, expand=True, resample=Image.Resampling.BICUBIC)
    rw, rh = rot.size
    base.paste(rot, (int(cx - rw / 2), int(cy - rh / 2)), rot)


def _cv_canvas(rows):
    canvas = Image.new("RGB", (800, 500), "white")
    draw = ImageDraw.Draw(canvas)
    marks = cv_k_marks(rows)
    font = load_font(15)
    font_s = load_font(13)
    ink = (51, 51, 51, 255)
    if not marks:
        message = "No CV error to plot"
        tw, th = text_wh(font, message)
        draw.text(((800 - tw) / 2, (500 - th) / 2), message, font=font, fill=(51, 51, 51))
        return canvas
    left, right = 86, 776
    top, bottom = 46, 420
    vals = []
    for row in rows:
        if row["cv_error"] == "NA" or not str(row["k"]).isdigit():
            continue
        vals.append(float(row["cv_error"]))
    ymin = min(vals)
    ymax = max(vals)
    if ymax == ymin:
        pad = 1.0 if ymax == 0 else abs(ymax) * 0.05
        if pad == 0:
            pad = 1.0
    else:
        pad = (ymax - ymin) * 0.12
    ymin -= pad
    ymax += pad
    span = ymax - ymin

    def y_of(value):
        return bottom - (value - ymin) / span * (bottom - top)

    n_k = len(marks)
    span_left = left + 28
    span_right = right - 28
    if n_k == 1:
        xs = [(span_left + span_right) / 2.0]
    else:
        xs = [
            span_left + (span_right - span_left) * i / (n_k - 1)
            for i in range(n_k)
        ]
    draw.line([(left, top), (left, bottom), (right, bottom)], fill=(51, 51, 51), width=1)
    _paste_up(canvas, "CV error", font, ink, 18, (top + bottom) / 2)
    kw, kh = text_wh(font, "K")
    draw.text(((left + right - kw) / 2, 464), "K", font=font, fill=(51, 51, 51))
    for step in range(5):
        value = ymin + span * step / 4.0
        y = y_of(value)
        draw.line([(left - 4, y), (left, y)], fill=(51, 51, 51), width=1)
        label = _ascii_tick(value)
        tw, th = text_wh(font_s, label)
        draw.text((left - 8 - tw, y - th / 2), label, font=font_s, fill=(51, 51, 51))
    by_k = {mark["k"]: x for mark, x in zip(marks, xs)}
    for mark, x in zip(marks, xs):
        y0 = y_of(mark["vmin"])
        y1 = y_of(mark["vmax"])
        draw.line([(x, y0), (x, y1)], fill=(136, 136, 136), width=2)
        cy = int(round(y_of(mark["median"])))
        cx = int(round(x))
        draw.line([(cx - 6, cy), (cx + 5, cy)], fill=(176, 0, 0), width=3)
        nlab = "n=%d" % mark["n"]
        tw, th = text_wh(font_s, nlab)
        draw.text((x - tw / 2, 16), nlab, font=font_s, fill=(51, 51, 51))
        klab = str(mark["k"])
        tw, th = text_wh(font_s, klab)
        draw.text((x - tw / 2, bottom + 8), klab, font=font_s, fill=(51, 51, 51))
    for row in rows:
        if row["cv_error"] == "NA" or not str(row["k"]).isdigit():
            continue
        k = int(row["k"])
        x = by_k[k]
        y = y_of(float(row["cv_error"]))
        draw.ellipse((x - 4, y - 4, x + 4, y + 4), fill=(51, 51, 51))
    return canvas


def write_cv_loglik_plot(png_path, rows):
    """Write an 800 by 500 CV plot as PNG and PDF.

    Figure text is the ASCII strings ``K``, ``CV error``, ``n=<count>``,
    and, when no numeric CV is present, ``No CV error to plot``.
    """
    canvas = _cv_canvas(rows)
    folder = os.path.dirname(os.path.abspath(png_path))
    if folder:
        os.makedirs(folder, exist_ok=True)
    canvas.save(png_path, dpi=(150, 150))
    canvas.save(os.path.splitext(png_path)[0] + ".pdf", "PDF", resolution=150.0)
