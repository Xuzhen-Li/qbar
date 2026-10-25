"""Vector PDF and SVG for the bar figure.

Coordinates are the same pixel positions ``render`` uses. One SVG user
unit is one pixel. PDF points are ``72/150`` per pixel, so the page
matches the raster PDF page size. Bars are one rectangle per sample per
column with a positive height. Equal neighbours are not merged.

SVG names the font and does not embed it. PDF embeds the TrueType file
from ``FONT_CANDIDATES`` as a ``FontFile2`` and accepts ASCII text only.
Pillow is imported inside the font helpers, not at import time.
"""
from __future__ import annotations

import math
import os
import struct
import zlib

from .messages import text as _msg

# Rectangles in one vector file. Equality is allowed.
VECTOR_RECT_CAP = 200000

_PDF_SCALE = 72.0 / 150.0

_FONT_FACE = {}
_FONT_RESOURCE = {}


def _resolve_cap(rect_cap):
    if rect_cap is None:
        return VECTOR_RECT_CAP
    return int(rect_cap)


def font_file(language="en"):
    """First existing path in ``FONT_CANDIDATES``.

    A missing file is a ``SystemExit``. Vector output does not fall back
    to a bitmap font.
    """
    from .plot_static import FONT_CANDIDATES
    for path in FONT_CANDIDATES:
        if os.path.isfile(path):
            return path
    raise SystemExit(_msg("vector_font_missing", language))


def count_bar_rectangles(rows):
    """How many bar rectangles these rows would draw.

    A cell is drawn when its Q value is greater than 0. Legend swatches
    are not included. ``rows`` entries need a ``q`` matrix in draw order.
    """
    total = 0
    for row in rows:
        q = _row_q(row)
        n = len(q)
        if n == 0:
            continue
        k = len(q[0])
        for i in range(n):
            for c in range(k):
                if float(q[i][c]) > 0.0:
                    total += 1
    return total


def vector_paths(png_path, mode):
    """PDF and SVG paths a bar PNG would gain for ``mode``."""
    stem = os.path.splitext(png_path)[0]
    paths = []
    if mode in ("pdf", "both"):
        paths.append(stem + ".pdf")
    if mode in ("svg", "both"):
        paths.append(stem + ".svg")
    return paths


def guard_vector_run(figures, spans, bar_w, title, dendrogram, mode, *, language="en", rect_cap=None):
    """Refuse before any figure file is written.

    ``figures`` is a list of ``{"png", "rows", "bar_h"}``. Every vector
    path is counted first. One file above the cap raises, and the caller
    writes nothing. PDF text is checked after the cap, still before writing.
    """
    if mode == "off":
        return
    if mode not in ("pdf", "svg", "both"):
        raise SystemExit(_msg("vector_choice", language, got=mode))
    font_file(language)
    cap = _resolve_cap(rect_cap)
    over = []
    for fig in figures:
        count = count_bar_rectangles(fig["rows"])
        for path in vector_paths(fig["png"], mode):
            if count > cap:
                over.append((os.path.basename(path), count))
    if over:
        parts = [
            _msg("vector_rect_cap", language, kind=kind, count=count, cap=cap)
            for kind, count in over
        ]
        raise SystemExit(" ".join(parts))
    if mode in ("pdf", "both"):
        for fig in figures:
            _reject_non_ascii(
                fig["rows"], spans, bar_w, fig["bar_h"], title, dendrogram, language,
            )


def render_vector(path, rows, spans, bar_w, bar_h, title, *, language="en", dendrogram=None, rect_cap=None):
    """Write one vector PDF or SVG. Arguments mirror ``render``.

    ``rows`` is the same list ``render`` receives, and each row also has
    ``q`` in draw order. The cap is checked before the file is opened.
    ``rect_cap`` overrides ``VECTOR_RECT_CAP`` for tests. ``None`` uses
    the module constant.
    """
    ext = os.path.splitext(path)[1].lower()
    if ext == ".pdf":
        mode = "pdf"
    elif ext == ".svg":
        mode = "svg"
    else:
        raise SystemExit(_msg("vector_ext", language, path=path))
    guard_vector_run(
        [{"png": os.path.splitext(path)[0] + ".png", "rows": rows, "bar_h": bar_h}],
        spans, bar_w, title, dendrogram, mode,
        language=language, rect_cap=rect_cap,
    )
    scene = _build_scene(rows, spans, bar_w, bar_h, title, dendrogram, language)
    if ext == ".svg":
        payload = _svg_bytes(scene)
    else:
        payload = _pdf_bytes(scene)
    folder = os.path.dirname(os.path.abspath(path))
    if folder:
        os.makedirs(folder, exist_ok=True)
    with open(path, "wb") as handle:
        handle.write(payload)
    return path


def _row_q(row):
    if "q" not in row:
        raise SystemExit(_msg("vector_rows", "en"))
    return row["q"]


def _hexes_of(row, k, language):
    hexes = [hx for hx, _text in row["legend"]]
    if len(hexes) != k:
        raise SystemExit(_msg("vector_rows", language))
    return hexes


def _is_ascii_text(text):
    for ch in text:
        code = ord(ch)
        if code < 32 or code > 126:
            return False
    return True


def _reject_non_ascii(rows, spans, bar_w, bar_h, title, dendrogram, language):
    font_path = font_file(language)
    for label in _drawn_labels(rows, spans, bar_w, bar_h, title, dendrogram, font_path):
        if not _is_ascii_text(label):
            raise SystemExit(_msg("vector_pdf_ascii", language, label=label))


def _pil_font(path, size):
    key = (path, int(size))
    font = _FONT_FACE.get(key)
    if font is None:
        from PIL import ImageFont
        font = ImageFont.truetype(path, int(size))
        _FONT_FACE[key] = font
    return font


def _text_wh(font, text):
    from .plot_static import text_wh
    return text_wh(font, text)


def _layout(rows, spans, bar_w, bar_h, title, dendrogram, font_path):
    """Pixel layout copied from ``render``."""
    from .plot_static import BAR_LEFT, dendrogram_height
    font = _pil_font(font_path, 15)
    font_s = _pil_font(font_path, 13)
    font_k = _pil_font(font_path, 16)
    title_font = _pil_font(font_path, 18)
    font_d = _pil_font(font_path, 11)
    left = BAR_LEFT
    gap = 12
    leg_w = 0
    for row in rows:
        for _hx, text in row["legend"]:
            leg_w = max(leg_w, _text_wh(font_s, text)[0] + 22)
    leg_w = min(max(leg_w, 80), 420)
    names = [s["name"] for s in spans]
    longest = max([_text_wh(font, s)[0] for s in names], default=0)
    rotate = len(spans) > 12 or (spans and bar_w / len(spans) < longest + 8)
    if rotate:
        label_h = int(longest * 0.75) + 28
    else:
        label_h = _text_wh(font, "Ag")[1] + 16
    title_h = 32 if title else 8
    row_pitch = []
    for row in rows:
        need = 4 + len(row["legend"]) * 18
        row_pitch.append(max(bar_h, need))
    n = rows[0]["image"].shape[1]
    dendro_h = dendrogram_height(dendrogram) if dendrogram else 0
    width = left + bar_w + gap + leg_w + 16
    height = title_h + dendro_h + sum(row_pitch) + label_h + 12
    return {
        "font": font,
        "font_s": font_s,
        "font_k": font_k,
        "title_font": title_font,
        "font_d": font_d,
        "left": left,
        "gap": gap,
        "rotate": rotate,
        "title_h": title_h,
        "row_pitch": row_pitch,
        "n": n,
        "dendro_h": dendro_h,
        "width": width,
        "height": height,
        "font_path": font_path,
    }


def _drawn_labels(rows, spans, bar_w, bar_h, title, dendrogram, font_path):
    """Text ``render`` actually draws, in paint order."""
    from .plot_static import (
        dendrogram_distance_label,
        span_bounds,
        _spec_max_distance,
    )
    lay = _layout(rows, spans, bar_w, bar_h, title, dendrogram, font_path)
    labels = []
    if title:
        labels.append(title)
    if lay["dendro_h"]:
        max_d = _spec_max_distance(dendrogram)
        if max_d is not None:
            labels.append(dendrogram_distance_label(max_d))
    for row in rows:
        labels.append("K%d" % row["k"])
        for _hx, text in row["legend"]:
            labels.append(text)
    for span in spans:
        px0, px1 = span_bounds(span, lay["n"], bar_w, lay["left"])
        if px1 - px0 < 14:
            continue
        labels.append(span["name"])
    return labels


def _build_scene(rows, spans, bar_w, bar_h, title, dendrogram, language):
    from .plot_static import (
        DENDRO_INK,
        dendrogram_distance_label,
        layer_leaf_xs,
        span_bounds,
        span_centre,
        _linkage_segments,
        _px_per_distance,
        _spec_max_distance,
    )
    font_path = font_file(language)
    lay = _layout(rows, spans, bar_w, bar_h, title, dendrogram, font_path)
    ink = (31, 41, 55)
    commands = []
    if title:
        commands.append(("text", lay["left"], 6, title, 18, ink))
    if lay["dendro_h"]:
        max_d = _spec_max_distance(dendrogram)
        if max_d is not None:
            px_per = _px_per_distance(max_d)
            y_bottom = lay["title_h"] + lay["dendro_h"]
            for layer in dendrogram.get("layers") or []:
                leaf_x = layer_leaf_xs(layer, lay["n"], bar_w, lay["left"], language=language)
                segments, _layer_max = _linkage_segments(layer["Z"], leaf_x, language=language)
                for x1, d1, x2, d2 in segments:
                    y1 = y_bottom - d1 * px_per
                    y2 = y_bottom - d2 * px_per
                    commands.append(("line", float(x1), float(y1), float(x2), float(y2), DENDRO_INK, 1))
            commands.append((
                "text", 8, lay["title_h"], dendrogram_distance_label(max_d), 11, DENDRO_INK,
            ))
    y = lay["title_h"] + lay["dendro_h"]
    for row, pitch in zip(rows, lay["row_pitch"]):
        q = _row_q(row)
        if len(q) != lay["n"]:
            raise SystemExit(_msg("vector_rows", language))
        k = len(q[0]) if lay["n"] else 0
        hexes = _hexes_of(row, k, language) if lay["n"] else []
        bar_y = y + (pitch - bar_h) // 2
        commands.extend(_bar_commands(q, hexes, lay["left"], bar_w, bar_y, bar_h))
        commands.append((
            "text", 8, bar_y + bar_h // 2 - 8, "K%d" % row["k"], 16, ink,
        ))
        lx = lay["left"] + bar_w + lay["gap"]
        ly = y + 2
        for hx, text in row["legend"]:
            commands.append(("swatch", lx, ly + 2, 12, 12, hx))
            commands.append(("text", lx + 16, ly, text, 13, ink))
            ly += 18
        y += pitch
    boundary = (148, 163, 184)
    bar_top = lay["title_h"] + lay["dendro_h"]
    for span in spans:
        if span["start"] <= 0:
            continue
        x = span_bounds(span, lay["n"], bar_w, lay["left"])[0]
        commands.append((
            "line", x, bar_top, x, bar_top + sum(lay["row_pitch"]), boundary, 1,
        ))
    y_lab = bar_top + sum(lay["row_pitch"]) + 4
    for span in spans:
        px0, px1 = span_bounds(span, lay["n"], bar_w, lay["left"])
        if px1 - px0 < 14:
            continue
        mid = span_centre(span, lay["n"], bar_w, lay["left"])
        if lay["rotate"]:
            commands.append(("text45", mid - 6, y_lab, span["name"], 13, ink))
        else:
            tw, _th = _text_wh(lay["font"], span["name"])
            commands.append(("text", mid - tw // 2, y_lab, span["name"], 15, ink))
    family = _font_resource(font_path)["family"]
    return {
        "width": lay["width"],
        "height": lay["height"],
        "commands": commands,
        "font_path": font_path,
        "family": family,
    }


def _bar_commands(q, hexes, left, bar_w, bar_y, bar_h):
    """One rectangle per positive cell inside the bar.

    ``x = left + i * bar_w / n``. Each sample except the last is 0.5 px
    wider, extending right into the next sample. Each stacked segment
    except the one that reaches the top of the bar is 0.5 px taller,
    extending up into the next segment. The outer edges of the bar block
    stay put.

    A column is clipped to the cumulative interval [0, 1]. That is the
    same limit as the raster bar: a pixel's share coordinate stays below
    1, and a column past that share is left unpainted.
    """
    n = len(q)
    if n <= 0:
        return []
    width = float(bar_w) / float(n)
    commands = []
    for i in range(n):
        x = float(left) + i * width
        sample_w = width if i == n - 1 else width + 0.5
        total = 0.0
        row = q[i]
        for c in range(len(row)):
            frac = float(row[c])
            start = total
            total += frac
            if frac <= 0.0:
                continue
            vis_lo = start
            vis_hi = total
            if vis_hi <= 0.0 or vis_lo >= 1.0:
                continue
            if vis_lo < 0.0:
                vis_lo = 0.0
            if vis_hi > 1.0:
                vis_hi = 1.0
            if vis_hi <= vis_lo:
                continue
            y = float(bar_y) + float(bar_h) - vis_hi * float(bar_h)
            height = (vis_hi - vis_lo) * float(bar_h)
            if vis_hi < 1.0:
                y -= 0.5
                height += 0.5
            commands.append(("bar", x, y, sample_w, height, hexes[c]))
    return commands


def _num(value):
    text = "%.6f" % float(value)
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    if text in ("", "-0"):
        return "0"
    return text


def _xml(text):
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _svg_fill(color):
    if isinstance(color, str):
        h = color.lstrip("#")
        rgb = tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
    else:
        rgb = tuple(int(channel) for channel in color[:3])
    return "#%02x%02x%02x" % rgb


def _family_list(family):
    cleaned = family.replace("\\", "").replace('"', "").replace("'", "")
    if any(ch in cleaned for ch in " ,;"):
        named = "'%s'" % cleaned
    else:
        named = cleaned
    return "%s, sans-serif" % named


def _svg_bytes(scene):
    family = _family_list(scene["family"])
    width = scene["width"]
    height = scene["height"]
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d" font-family="%s">' % (
            width, height, width, height, _xml(family),
        ),
        "<!-- This file names the font and does not embed it. -->",
        '<path fill="#ffffff" d="M0 0H%dV%dH0Z"/>' % (width, height),
    ]
    fonts = {}
    for command in scene["commands"]:
        kind = command[0]
        if kind == "bar":
            _x, x, y, w, h, fill = command
            lines.append(
                '<rect x="%s" y="%s" width="%s" height="%s" fill="%s"/>' % (
                    _num(x), _num(y), _num(w), _num(h), _svg_fill(fill),
                )
            )
        elif kind == "swatch":
            _x, x, y, w, h, fill = command
            lines.append(
                '<path fill="%s" d="M%s %sH%sV%sH%sZ"/>' % (
                    _svg_fill(fill), _num(x), _num(y), _num(x + w), _num(y + h), _num(x),
                )
            )
        elif kind == "line":
            _x, x1, y1, x2, y2, color, stroke = command
            lines.append(
                '<line x1="%s" y1="%s" x2="%s" y2="%s" stroke="%s" stroke-width="%s"/>' % (
                    _num(x1), _num(y1), _num(x2), _num(y2), _svg_fill(color), _num(stroke),
                )
            )
        elif kind == "text":
            _x, x, y, text, size, color = command
            baseline = y + _ascent(scene["font_path"], size, fonts)
            lines.append(
                '<text x="%s" y="%s" font-size="%d" fill="%s">%s</text>' % (
                    _num(x), _num(baseline), int(size), _svg_fill(color), _xml(text),
                )
            )
        elif kind == "text45":
            _x, paste_x, paste_y, text, size, color = command
            bx, by = _rotated_baseline(scene["font_path"], text, size, paste_x, paste_y, fonts)
            lines.append(
                '<text x="0" y="0" transform="translate(%s %s) rotate(-45)" font-size="%d" fill="%s">%s</text>' % (
                    _num(bx), _num(by), int(size), _svg_fill(color), _xml(text),
                )
            )
        else:
            raise SystemExit(_msg("vector_rows", "en"))
    lines.append("</svg>")
    return ("\n".join(lines) + "\n").encode("utf-8")


def _ascent(path, size, cache):
    key = int(size)
    if key not in cache:
        cache[key] = _pil_font(path, key).getmetrics()[0]
    return cache[key]


def _rotated_baseline(path, text, size, paste_x, paste_y, cache):
    """Baseline point after the same 45 degree expand rotation as ``draw_rotated``."""
    font = _pil_font(path, int(size))
    w, h = _text_wh(font, text)
    matrix = _pillow_expand_matrix(w + 4, h + 4, 45.0)
    bx, by = _invert_affine(matrix, 1.0, float(_ascent(path, size, cache)))
    return float(int(paste_x)) + bx, float(int(paste_y)) + by


def _pillow_expand_matrix(w, h, angle_deg):
    """Output-to-input affine from Pillow's rotate(..., expand=True)."""
    angle = -math.radians(angle_deg % 360.0)
    center = (w / 2.0, h / 2.0)
    matrix = [
        round(math.cos(angle), 15),
        round(math.sin(angle), 15),
        0.0,
        round(-math.sin(angle), 15),
        round(math.cos(angle), 15),
        0.0,
    ]

    def transform(x, y):
        a, b, c, d, e, f = matrix
        return a * x + b * y + c, d * x + e * y + f

    matrix[2], matrix[5] = transform(-center[0], -center[1])
    matrix[2] += center[0]
    matrix[5] += center[1]
    xs = []
    ys = []
    for x, y in ((0, 0), (w, 0), (w, h), (0, h)):
        tx, ty = transform(x, y)
        xs.append(tx)
        ys.append(ty)
    nw = math.ceil(max(xs)) - math.floor(min(xs))
    nh = math.ceil(max(ys)) - math.floor(min(ys))
    matrix[2], matrix[5] = transform(-(nw - w) / 2.0, -(nh - h) / 2.0)
    return matrix


def _invert_affine(matrix, x_in, y_in):
    a, b, c, d, e, f = matrix
    det = a * e - b * d
    x_out = (e * (x_in - c) - b * (y_in - f)) / det
    y_out = (-d * (x_in - c) + a * (y_in - f)) / det
    return x_out, y_out


def _ttf_table(data, tag):
    num = struct.unpack(">H", data[4:6])[0]
    for index in range(num):
        off = 12 + index * 16
        found, _checksum, start, length = struct.unpack(">4sIII", data[off:off + 16])
        if found == tag:
            return data[start:start + length]
    return b""


def _ttf_name(data, name_id):
    table = _ttf_table(data, b"name")
    if len(table) < 6:
        return ""
    _fmt, count, string_offset = struct.unpack(">HHH", table[:6])
    best = None
    for index in range(count):
        rec = table[6 + index * 12:6 + (index + 1) * 12]
        if len(rec) < 12:
            break
        plat, enc, lang, nid, length, offset = struct.unpack(">HHHHHH", rec)
        if nid != name_id:
            continue
        raw = table[string_offset + offset:string_offset + offset + length]
        if plat == 3 and enc in (1, 10):
            text = raw.decode("utf-16-be", "replace").replace("\x00", "")
            score = 2 if lang in (0x0409, 0x0809, 0x0C09) else 1
        elif plat == 1 and enc == 0:
            text = raw.decode("mac-roman", "replace").replace("\x00", "")
            score = 0
        else:
            continue
        if best is None or score > best[0]:
            best = (score, text)
    if best is None:
        return ""
    return best[1]


def _pdf_name(text):
    out = []
    for ch in text:
        if ch.isalnum():
            out.append(ch)
        elif ch in "-_":
            out.append(ch)
        elif ord(ch) < 128:
            out.append("#%02X" % ord(ch))
    if not out:
        return "QbarFont"
    return "".join(out)


def _font_resource(path):
    cached = _FONT_RESOURCE.get(path)
    if cached is not None:
        return cached
    with open(path, "rb") as handle:
        data = handle.read()
    from PIL import ImageFont
    family, _style = ImageFont.truetype(path, 32).getname()
    ps = _ttf_name(data, 6) or family.replace(" ", "")
    measure = ImageFont.truetype(path, 1000)
    widths = [int(round(measure.getlength(chr(code)))) for code in range(32, 127)]
    head = _ttf_table(data, b"head")
    units = struct.unpack(">H", head[18:20])[0] or 1000
    x_min, y_min, x_max, y_max = struct.unpack(">hhhh", head[36:44])
    hhea = _ttf_table(data, b"hhea")
    ascent, descent = struct.unpack(">hh", hhea[4:8])

    def scale(value):
        return int(round(float(value) * 1000.0 / float(units)))

    cap = scale(int(round(ascent * 0.7)))
    os2 = _ttf_table(data, b"OS/2")
    if len(os2) >= 90:
        version = struct.unpack(">H", os2[:2])[0]
        if version >= 2:
            raw_cap = struct.unpack(">h", os2[88:90])[0]
            if raw_cap > 0:
                cap = scale(raw_cap)
    cached = {
        "bytes": data,
        "family": family,
        "ps": _pdf_name(ps),
        "widths": widths,
        "bbox": (scale(x_min), scale(y_min), scale(x_max), scale(y_max)),
        "ascent": scale(ascent),
        "descent": scale(descent),
        "cap": cap,
    }
    _FONT_RESOURCE[path] = cached
    return cached


def _pdf_string(text):
    out = ["("]
    for ch in text:
        if ch in "()\\":
            out.append("\\" + ch)
        else:
            out.append(ch)
    out.append(")")
    return "".join(out)


def _pdf_rgb(color):
    if isinstance(color, str):
        h = color.lstrip("#")
        channels = [int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]
    else:
        channels = [int(channel) / 255.0 for channel in color[:3]]
    return " ".join(_num(channel) for channel in channels)


def _pdf_content(scene):
    page_h = float(scene["height"])
    scale = _PDF_SCALE
    fonts = {}
    lines = []

    def pt_x(x):
        return float(x) * scale

    def pt_y(y):
        return (page_h - float(y)) * scale

    for command in scene["commands"]:
        kind = command[0]
        if kind in ("bar", "swatch"):
            _x, x, y, w, h, fill = command
            x0 = pt_x(x)
            y0 = pt_y(y + h)
            lines.append("%s rg" % _pdf_rgb(fill))
            if kind == "bar":
                lines.append("%s %s %s %s re" % (_num(x0), _num(y0), _num(pt_x(w)), _num(h * scale)))
                lines.append("f")
            else:
                x1 = pt_x(x + w)
                y1 = pt_y(y)
                lines.append("%s %s m" % (_num(x0), _num(y0)))
                lines.append("%s %s l" % (_num(x1), _num(y0)))
                lines.append("%s %s l" % (_num(x1), _num(y1)))
                lines.append("%s %s l" % (_num(x0), _num(y1)))
                lines.append("h")
                lines.append("f")
        elif kind == "line":
            _x, x1, y1, x2, y2, color, stroke = command
            lines.append("%s w" % _num(float(stroke) * scale))
            lines.append("%s RG" % _pdf_rgb(color))
            lines.append("%s %s m" % (_num(pt_x(x1)), _num(pt_y(y1))))
            lines.append("%s %s l" % (_num(pt_x(x2)), _num(pt_y(y2))))
            lines.append("S")
        elif kind == "text":
            _x, x, y, text, size, color = command
            baseline = y + _ascent(scene["font_path"], size, fonts)
            _pdf_text(lines, text, size, color, pt_x(x), pt_y(baseline), None)
        elif kind == "text45":
            _x, paste_x, paste_y, text, size, color = command
            bx, by = _rotated_baseline(scene["font_path"], text, size, paste_x, paste_y, fonts)
            angle = math.radians(45.0)
            cos = math.cos(angle)
            sin = math.sin(angle)
            _pdf_text(
                lines, text, size, color, pt_x(bx), pt_y(by), (cos, sin, -sin, cos),
            )
        else:
            raise SystemExit(_msg("vector_rows", "en"))
    return ("\n".join(lines) + "\n").encode("ascii")


def _pdf_text(lines, text, size, color, x_pt, y_pt, matrix):
    size_pt = float(size) * _PDF_SCALE
    if matrix is None:
        a, b, c, d = 1, 0, 0, 1
    else:
        a, b, c, d = matrix
    lines.append("BT")
    lines.append("/F1 %s Tf" % _num(size_pt))
    lines.append("%s rg" % _pdf_rgb(color))
    lines.append("%s %s %s %s %s %s Tm" % (
        _num(a), _num(b), _num(c), _num(d), _num(x_pt), _num(y_pt),
    ))
    lines.append("%s Tj" % _pdf_string(text))
    lines.append("ET")


def _pdf_bytes(scene):
    font = _font_resource(scene["font_path"])
    content = zlib.compress(_pdf_content(scene), 9)
    font_stream = zlib.compress(font["bytes"], 9)
    page_w = float(scene["width"]) * _PDF_SCALE
    page_h = float(scene["height"]) * _PDF_SCALE
    widths = " ".join(str(item) for item in font["widths"])
    x_min, y_min, x_max, y_max = font["bbox"]
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>\n",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>\n",
        (
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 %s %s] /Contents 4 0 R "
            "/Resources << /Font << /F1 5 0 R >> >> >>\n" % (_num(page_w), _num(page_h))
        ).encode("ascii"),
        (
            b"<< /Length %d /Filter /FlateDecode >>\nstream\n" % len(content)
            + content
            + b"\nendstream\n"
        ),
        (
            "<< /Type /Font /Subtype /TrueType /BaseFont /%s /Encoding /WinAnsiEncoding "
            "/FirstChar 32 /LastChar 126 /Widths [%s] /FontDescriptor 6 0 R >>\n" % (
                font["ps"], widths,
            )
        ).encode("ascii"),
        (
            "<< /Type /FontDescriptor /FontName /%s /Flags 32 /FontBBox [%d %d %d %d] "
            "/ItalicAngle 0 /Ascent %d /Descent %d /CapHeight %d /StemV 80 /FontFile2 7 0 R >>\n" % (
                font["ps"], x_min, y_min, x_max, y_max,
                font["ascent"], font["descent"], font["cap"],
            )
        ).encode("ascii"),
        (
            b"<< /Length %d /Length1 %d /Filter /FlateDecode >>\nstream\n" % (
                len(font_stream), len(font["bytes"]),
            )
            + font_stream
            + b"\nendstream\n"
        ),
    ]
    return _assemble_pdf(objects)


def _assemble_pdf(objects):
    chunks = [b"%PDF-1.4\n"]
    offsets = []
    for index, body in enumerate(objects, 1):
        offsets.append(sum(len(chunk) for chunk in chunks))
        chunks.append(b"%d 0 obj\n" % index)
        chunks.append(body)
        chunks.append(b"endobj\n")
    xref_at = sum(len(chunk) for chunk in chunks)
    xref = [b"xref\n", b"0 %d\n" % (len(objects) + 1), b"0000000000 65535 f \n"]
    for offset in offsets:
        xref.append(b"%010d 00000 n \n" % offset)
    trailer = (
        b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n"
        % (len(objects) + 1, xref_at)
    )
    return b"".join(chunks + xref + [trailer])
