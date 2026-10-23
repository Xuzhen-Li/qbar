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


def _select_points(table, key):
    points = []
    for row in table:
        text = row.get(key, "NA")
        if text == "NA":
            continue
        points.append((int(row["k"]), float(text)))
    return points


def _draw_select_panel(canvas, origin_y, title, points):
    """One 300 px band. A band with no points shows ``No data``."""
    draw = ImageDraw.Draw(canvas)
    font = load_font(15)
    font_s = load_font(13)
    width = canvas.size[0]
    ink = (51, 51, 51)
    draw.text((16, origin_y + 8), title, font=font, fill=ink)
    if not points:
        message = "No data"
        tw, th = text_wh(font, message)
        draw.text(
            ((width - tw) / 2, origin_y + (300 - th) / 2),
            message,
            font=font,
            fill=ink,
        )
        return
    left, right = 78, 860
    top = origin_y + 40
    bottom = origin_y + 246
    vals = [value for _k, value in points]
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

    n_k = len(points)
    span_left = left + 24
    span_right = right - 24
    if n_k == 1:
        xs = [(span_left + span_right) / 2.0]
    else:
        xs = [
            span_left + (span_right - span_left) * i / (n_k - 1)
            for i in range(n_k)
        ]
    draw.line([(left, top), (left, bottom), (right, bottom)], fill=ink, width=1)
    for step in range(5):
        value = ymin + span * step / 4.0
        y = y_of(value)
        label = _ascii_tick(value)
        tw, th = text_wh(font_s, label)
        draw.line([(left - 4, y), (left, y)], fill=ink, width=1)
        draw.text((left - 8 - tw, y - th / 2), label, font=font_s, fill=ink)
    if n_k > 1:
        coords = []
        for (_k, value), x in zip(points, xs):
            coords.extend((x, y_of(value)))
        draw.line(coords, fill=(136, 136, 136), width=2)
    for (k, value), x in zip(points, xs):
        y = y_of(value)
        draw.ellipse((x - 4, y - 4, x + 4, y + 4), fill=ink)
        klab = str(k)
        tw, th = text_wh(font_s, klab)
        draw.text((x - tw / 2, bottom + 6), klab, font=font_s, fill=ink)
    kw, _kh = text_wh(font_s, "K")
    draw.text(((left + right - kw) / 2, bottom + 24), "K", font=font_s, fill=ink)


def _select_k_canvas(table):
    canvas = Image.new("RGB", (900, 900), "white")
    panels = (
        ("CV error", _select_points(table, "cv_median")),
        ("log-likelihood", _select_points(table, "loglik_mean")),
        ("deltaK", _select_points(table, "delta_k")),
    )
    for index, (title, points) in enumerate(panels):
        _draw_select_panel(canvas, index * 300, title, points)
    return canvas


def write_select_k_plot(png_path, table):
    """Write a 900 by 900 select-K plot as PNG and PDF.

    Three stacked panels, titled ``CV error``, ``log-likelihood``, and
    ``deltaK``. Each panel draws one point per K. A panel with no numeric
    values shows ``No data``. Labels are ASCII. The PDF uses the same
    Pillow save as the bar plot, resolution 150.
    """
    canvas = _select_k_canvas(table)
    folder = os.path.dirname(os.path.abspath(png_path))
    if folder:
        os.makedirs(folder, exist_ok=True)
    canvas.save(png_path, dpi=(150, 150))
    if png_path.lower().endswith(".png"):
        canvas.save(os.path.splitext(png_path)[0] + ".pdf", "PDF", resolution=150.0)


# Fixed canvas. The PDF uses the same Pillow save as the bar plot.
FLOW_CANVAS = (960, 640)
FLOW_FIGURE_TITLE = "membership weight"
FLOW_NODE_CAPTION = "Node height is the mean membership of that column."
FLOW_BAND_CAPTION = (
    "Band thickness is weight times the destination column sum over the "
    "rows used for that step, divided by all rows."
)


def _px(value):
    """Nearest integer, half away from zero for positive values."""
    return int(float(value) + 0.5)


def _mix_white(h, keep=0.65):
    rgb = hex_rgb(h)
    mixed = []
    for channel in rgb:
        mixed.append(int(float(channel) * keep + 255.0 * (1.0 - keep) + 0.5))
    return tuple(mixed)


def _ink_on(h):
    rgb = hex_rgb(h)
    luma = 0.2126 * float(rgb[0]) + 0.7152 * float(rgb[1]) + 0.0722 * float(rgb[2])
    if luma < 150.0:
        return (255, 255, 255)
    return (31, 41, 55)


def flow_band_thickness(weight, masked_sum, n_all, scale):
    """Return ``weight * masked_sum / n_all * scale``.

    ``masked_sum`` is the destination column summed over the rows used
    for that step. ``n_all`` is every row. Node height stays the all-row
    mean times ``scale``. With every row used, ``masked_sum / n_all``
    is that mean, so the thickness matches ``weight * mean * scale``.
    """
    n_all = int(n_all)
    if n_all <= 0:
        return 0.0
    return float(weight) * float(masked_sum) / float(n_all) * float(scale)


def _column_means(q):
    """Mean of each column over every row. Non-finite or negative means are 0.

    The bar draws every person, so the node height uses this mean
    (sum over all rows, divided by the row count). Band thickness uses
    ``flow_band_thickness`` and the masked sum. A negative mean is
    drawn as height 0.
    """
    q = np.asarray(q, dtype=float)
    if q.ndim != 2:
        return []
    n_rows, n_cols = q.shape
    means = []
    for c in range(int(n_cols)):
        if n_rows == 0:
            means.append(0.0)
            continue
        value = float(np.mean(q[:, c]))
        if not np.isfinite(value) or value < 0.0:
            value = 0.0
        means.append(value)
    return means


def _flow_node_hex(hexes, k, c):
    """Colour of aligned column ``c`` at K, else the bar palette."""
    if hexes is not None and k in hexes and c < len(hexes[k]):
        return hexes[k][c]
    if c < len(PALETTE):
        return PALETTE[c]
    return hsv_hex(c)


def _ribbon(x0, y0_top, y0_bot, x1, y1_top, y1_bot):
    """One filled band. ``top`` is the smaller image y."""
    def edge(y_start, y_end):
        points = []
        for step in range(17):
            u = step / 16.0
            smooth = u * u * (3.0 - 2.0 * u)
            x = x0 + (x1 - x0) * u
            y = y_start + (y_end - y_start) * smooth
            points.append((_px(x), _px(y)))
        return points

    forward = edge(y0_top, y1_top)
    backward = edge(y0_bot, y1_bot)
    backward.reverse()
    return forward + backward


def _flow_canvas(aligned, edges, hexes):
    """960 by 640 RGB canvas.

    Node height is ``mean * scale``, with ``mean`` the all-row column
    mean. Column 0 (label C1) sits at the bottom, matching the bar.
    Bands are drawn for every edge. Thickness is ``flow_band_thickness``:
    weight times the destination column sum over the rows used for that
    step, divided by all rows, times ``scale``. Share weights that sum
    to 1 fill the masked part of the node. With every row used, that
    part is the node height. A thickness below half a pixel and above 0
    is raised to 1 pixel so a positive tie stays visible. Bands stack
    from the bottom of each node. Lower column index is closer to the
    bottom. A stack that runs past the node is still drawn.
    """
    width, height = FLOW_CANVAS
    canvas = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(canvas)
    font = load_font(15)
    font_s = load_font(13)
    ink = (51, 51, 51)
    left, right = 156, 800
    top, bottom = 84, 500
    gap = 4
    node_w = 36
    ks = sorted(aligned)
    means = {k: _column_means(aligned[k]) for k in ks}
    sums = [sum(cols) for cols in means.values()] or [0.0]
    max_sum = max(sums)
    n_cols = [len(cols) for cols in means.values()] or [0]
    max_gaps = gap * max(0, max(n_cols) - 1)
    usable = bottom - top
    if max_sum <= 0.0:
        scale = 0.0
        gap_px = float(gap)
    else:
        room = usable - max_gaps
        if room < 1.0:
            gap_px = 0.0
            room = float(usable)
        else:
            gap_px = float(gap)
        scale = room / max_sum
    if len(ks) <= 1:
        centers = [(left + right) / 2.0] if ks else []
    else:
        span = float(right - left)
        centers = [left + span * i / (len(ks) - 1) for i in range(len(ks))]
    boxes = {}
    for k, center in zip(ks, centers):
        y = float(bottom)
        boxes[k] = []
        cols = means[k]
        for index, mean in enumerate(cols):
            h = mean * scale
            y_bot = y
            y_top = y - h
            boxes[k].append((y_top, y_bot, mean, center))
            if index < len(cols) - 1:
                y = y_top - gap_px
    draw.line([(96, top), (96, bottom)], fill=ink, width=1)
    _paste_up(canvas, FLOW_FIGURE_TITLE, font, (ink[0], ink[1], ink[2], 255), 28, (top + bottom) / 2.0)
    weight_of = {}
    masked_of = {}
    for edge in edges:
        key = (
            int(edge["K_from"]),
            str(edge["col_from"]),
            int(edge["K_to"]),
            str(edge["col_to"]),
        )
        weight_of[key] = float(edge["weight"])
        masked_of[key] = float(edge["dest_masked_sum"])
    center_of = {k: center for k, center in zip(ks, centers)}
    for k_from, k_to in zip(ks, ks[1:]):
        src_boxes = boxes[k_from]
        dst_boxes = boxes[k_to]
        out_cursor = {s: src_boxes[s][1] for s in range(len(src_boxes))}
        in_cursor = {c: dst_boxes[c][1] for c in range(len(dst_boxes))}
        x0 = center_of[k_from] + node_w / 2.0
        x1 = center_of[k_to] - node_w / 2.0
        for s in range(len(src_boxes)):
            for c in range(len(dst_boxes)):
                label_from = "C%d" % (s + 1)
                label_to = "C%d" % (c + 1)
                key = (int(k_from), label_from, int(k_to), label_to)
                value = weight_of.get(key, 0.0)
                if value <= 0.0:
                    continue
                n_all = int(np.asarray(aligned[k_to]).shape[0])
                thick = flow_band_thickness(value, masked_of[key], n_all, scale)
                if 0.0 < thick < 0.5:
                    thick = 1.0
                if thick <= 0.0:
                    continue
                y0_bot = out_cursor[s]
                y0_top = y0_bot - thick
                out_cursor[s] = y0_top
                y1_bot = in_cursor[c]
                y1_top = y1_bot - thick
                in_cursor[c] = y1_top
                colour = _mix_white(_flow_node_hex(hexes, k_from, s))
                draw.polygon(
                    _ribbon(x0, y0_top, y0_bot, x1, y1_top, y1_bot),
                    fill=colour,
                )
    for k, center in zip(ks, centers):
        k_label = "K=%d" % int(k)
        tw, th = text_wh(font, k_label)
        draw.text((center - tw / 2.0, 36), k_label, font=font, fill=ink)
        for c, (y_top, y_bot, mean, _center) in enumerate(boxes[k]):
            colour = _flow_node_hex(hexes, k, c)
            top_i = _px(y_top)
            bot_i = _px(y_bot)
            if bot_i <= top_i and mean > 0.0:
                top_i = bot_i - 1
            x_left = _px(center - node_w / 2.0)
            x_right = _px(center + node_w / 2.0)
            if bot_i > top_i:
                rgb = tuple(int(channel) for channel in hex_rgb(colour))
                draw.rectangle((x_left, top_i, x_right, bot_i), fill=rgb)
            label = "C%d" % (c + 1)
            lw, lh = text_wh(font_s, label)
            if bot_i - top_i >= lh + 4:
                tx = (x_left + x_right - lw) / 2.0
                ty = (top_i + bot_i - lh) / 2.0
                draw.text((tx, ty), label, font=font_s, fill=_ink_on(colour))
            else:
                tx = x_right + 4
                ty = (top_i + bot_i - lh) / 2.0
                draw.rectangle(
                    (_px(tx) - 1, _px(ty) - 1, _px(tx + lw) + 1, _px(ty + lh) + 1),
                    fill=(255, 255, 255),
                )
                draw.text((tx, ty), label, font=font_s, fill=ink)
    draw.text((left, 524), FLOW_FIGURE_TITLE, font=font, fill=ink)
    draw.text((left, 552), FLOW_NODE_CAPTION, font=font_s, fill=ink)
    draw.text((left, 576), FLOW_BAND_CAPTION, font=font_s, fill=ink)
    return canvas


def write_cluster_flow_plot(png_path, aligned, edges, hexes=None):
    """Write ``cluster_flow.png`` and, for a .png path, ``cluster_flow.pdf``.

    The canvas is 960 by 640, white, RGB. Labels are ASCII. The axis
    title and the legend title are both ``membership weight``. Node
    height is the all-row column mean. Band thickness is
    ``flow_band_thickness``. Node colours are ``hexes[k]``, the same
    lists the bar plot uses. Without ``hexes``, columns take ``PALETTE``
    and then ``hsv_hex``. The PDF save matches the bar plot: Pillow
    ``resolution`` 150. Pillow is imported by this module; ``api.run``
    imports this module on the call.
    """
    canvas = _flow_canvas(aligned, edges, hexes)
    folder = os.path.dirname(os.path.abspath(png_path))
    if folder:
        os.makedirs(folder, exist_ok=True)
    canvas.save(png_path, dpi=(150, 150))
    if png_path.lower().endswith(".png"):
        canvas.save(os.path.splitext(png_path)[0] + ".pdf", "PDF", resolution=150.0)
    return png_path
