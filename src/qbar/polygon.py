"""Optional simplex / polygon plot.

Column k = 0, ..., K-1 is aligned column C(k+1). Vertex k sits at

    theta_k = pi/2 + 2 * pi * k / K

so C1 is at the top and the vertices go counter-clockwise. Those angles
were approved on 2026-10-22. Math y increases upward. The PNG flips y.

    (x, y) = sum_k q_k * (cos theta_k, sin theta_k)

This is the Q-weighted mean of the vertex coordinates. ``polygon_xy``
does not divide by the row sum. A row that does not sum to 1 is drawn
at that mean, and the TSV keeps the raw q.

K=3 has three vertices that are not on one line. A row that sums to 1
has one q for a point in the triangle. K>3 maps a (K-1)-dimensional
simplex into the plane, so different q can share one point. The K=4
rows (0.5, 0, 0.5, 0) and (0, 0.5, 0, 0.5) both land on (0, 0). When
K>3 the corner text is ``K>3: different Q can share one point``. When
K is 3 or less, that text is absent. K=1 is refused. K=2 draws the
segment between the top vertex and the bottom vertex.

The caller passes the rows to draw. ``run`` passes the aligned matrix
at ``--polygon-k`` (or the largest K), in bar order. An alignment mask
does not drop rows. The bar draws every row, and this figure uses the
same rows.

Vertex discs use the bar colours and the bar legend names for that K.
The design figure paints every sample the same blue and has no groups,
so it does not define a per-group colour. Group i in bar group order
uses tab10 colour i % 10. Marker shape follows the cycle i // 10:
circle, square, triangle pointing up, diamond, then the shapes repeat.
More than 10 groups add the legend line ``Colours repeat after 10
groups; marker shape changes.`` More than 40 groups also add ``Shapes
repeat after 40 groups.`` The legend draws each group's marker. A run
with no groups file paints every point ``#333333`` as a circle.

A vertex name that is wider than the space beside that vertex is
truncated with ``...``. A left label may use from canvas x=4 to its
anchor. A right label may use from its anchor to 4 px before the
gutter. A top or bottom label is centred and limited to the plot
square. One stderr note names each truncated vertex. The full name
stays in the bar legend.

Points are opaque. Alpha is not used. Groups are painted in bar group
order, so a later group covers an earlier group where they overlap.
Inside a group, samples follow bar order, and a later sample covers an
earlier one. Vertex discs are painted after the points.

The square plot is 1200 px, with a legend gutter. The picture is drawn
at twice that size and resized with Pillow's LANCZOS filter. Pillow is
imported only inside ``_draw``. ``--vector`` does not write a polygon
PDF or SVG.
"""
from __future__ import annotations

import math
import os
import sys

import numpy as np

from .messages import text as _msg

PLOT_PX = 1200
PAD_LEFT = 24
PAD_TOP = 48
PAD_BOTTOM = 24
GUTTER_PX = 320
RADIUS_PX = 420.0
SCALE = 2
VERTEX_R = 7.0
POINT_R = 3.0
POINT_R_LARGE = 2.0
LARGE_N = 5000
LABEL_GAP = 14.0
LABEL_MARGIN = 4.0
LEGEND_PITCH = 22
ELLIPSIS = "..."
OUTLINE = "#b0b0b0"
INK = (31, 41, 55)
UNGROUPED_COLOUR = "#333333"
CORNER_TEXT = "K>3: different Q can share one point"
CYCLE_NOTE = "Colours repeat after 10 groups; marker shape changes."
SHAPE_NOTE = "Shapes repeat after 40 groups."
MARKERS = ("circle", "square", "triangle", "diamond")

# matplotlib TABLEAU_COLORS, tag v3.9.2, source order.
# Same hex values as plot_static.TAB10_PALETTE. Copied here so importing
# this module does not import Pillow.
GROUP_COLOURS = (
    "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
    "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf",
)


def _exit(key, language, **values):
    raise SystemExit(_msg(key, language, **values))


def vertices(k):
    """Return vertex coordinates, shape ``(K, 2)``, math y upward.

    Row 0 is C1 at the top. Later rows go counter-clockwise.
    """
    count = int(k)
    if count < 1:
        raise ValueError("vertices expects K >= 1")
    theta = (np.pi / 2.0) + (2.0 * np.pi * np.arange(count, dtype=np.float64) / float(count))
    return np.column_stack((np.cos(theta), np.sin(theta)))


def polygon_xy(q):
    """Return ``(n, 2)`` weighted means. Does not renormalise rows."""
    matrix = np.asarray(q, dtype=np.float64)
    if matrix.ndim != 2 or matrix.shape[1] < 1:
        raise ValueError("polygon_xy expects an (n, K) array with K >= 1")
    basis = vertices(int(matrix.shape[1]))
    out = np.empty((int(matrix.shape[0]), 2), dtype=np.float64)
    out[:, 0] = matrix @ basis[:, 0]
    out[:, 1] = matrix @ basis[:, 1]
    return out


def _rgb(colour):
    text = str(colour).strip()
    if text[:1] == "#":
        text = text[1:]
    return (
        int(text[0:2], 16),
        int(text[2:4], 16),
        int(text[4:6], 16),
    )


def _clean_field(value, kind, row, language):
    shown = "" if value is None else str(value)
    if "\t" in shown or "\n" in shown or "\r" in shown:
        _exit("polygon_field", language, kind=kind, row=row)
    return shown


def _legend_names(legend, k, language):
    if legend is None:
        return ["C%d" % (index + 1) for index in range(k)]
    names = []
    for item in legend:
        if isinstance(item, (tuple, list)):
            if len(item) == 0:
                _exit("polygon_legend", language, k=k, got=0)
            names.append(str(item[-1]))
        else:
            names.append(str(item))
    if len(names) != k:
        _exit("polygon_legend", language, k=k, got=len(names))
    return names


def _label_place(math_x, math_y):
    """Pixel offset and Pillow anchor so the name sits outside the vertex."""
    if abs(math_y) >= abs(math_x):
        if math_y >= 0.0:
            return "mb", 0.0, -LABEL_GAP
        return "mt", 0.0, LABEL_GAP
    if math_x >= 0.0:
        return "lm", LABEL_GAP, 0.0
    return "rm", -LABEL_GAP, 0.0


def _label_room(vertex, plot, gutter_x):
    """Final-pixel width available for this vertex name.

    A left label runs from canvas x=4 to the anchor. A right label runs
    from the anchor to 4 px before the gutter. A top or bottom label is
    centred and stays inside the plot square.
    """
    anchor_x = float(vertex["x"]) + float(vertex["label_dx"])
    kind = vertex["label_anchor"]
    if kind == "rm":
        return anchor_x - LABEL_MARGIN
    if kind == "lm":
        return (gutter_x - LABEL_MARGIN) - anchor_x
    left = anchor_x - float(plot["x"])
    right = gutter_x - anchor_x
    centred = 2.0 * min(left, right)
    return min(float(plot["width"]), centred)


def _ink_width(font, text):
    box = font.getbbox(text)
    return box[2] - box[0]


def _clip_label(text, room_px, font, scale):
    """Return ``(shown, truncated)``. ``room_px`` is in final pixels."""
    room = float(room_px) * float(scale)
    if _ink_width(font, text) <= room:
        return text, False
    if _ink_width(font, ELLIPSIS) > room:
        return ELLIPSIS, True
    lo = 0
    hi = len(text)
    best = ELLIPSIS
    while lo <= hi:
        mid = (lo + hi) // 2
        candidate = text[:mid] + ELLIPSIS
        if _ink_width(font, candidate) <= room:
            best = candidate
            lo = mid + 1
        else:
            hi = mid - 1
    return best, best != text


def _fit_labels(geometry, language):
    """Truncate vertex names that do not fit. Prints one stderr note."""
    from .plot_static import load_font

    scale = int(geometry["scale"])
    font = load_font(13 * scale)
    plot = geometry["plot"]
    gutter_x = float(plot["x"]) + float(plot["width"])
    truncated = []
    for vertex in geometry["vertices"]:
        full = vertex["label"]
        vertex["label_full"] = full
        room = _label_room(vertex, plot, gutter_x)
        vertex["label_room"] = room
        shown, cut = _clip_label(full, room, font, scale)
        vertex["label"] = shown
        vertex["truncated"] = cut
        if cut:
            truncated.append("C%d" % (int(vertex["index"]) + 1))
    geometry["truncated_vertices"] = truncated
    if truncated:
        print(
            _msg("polygon_label_truncated", language, names=", ".join(truncated)),
            file=sys.stderr,
        )


def _note_lines(text):
    """Lines drawn for one legend note.

    The colour note is one sentence. The gutter is 320 px, and that
    sentence is wider than the gutter, so the draw splits it after the
    semicolon. The stored note stays the one sentence.
    """
    if not text:
        return []
    if "; " in text:
        head, tail = text.split("; ", 1)
        return [head + ";", tail]
    return [text]


def _marker_name(index):
    """Marker for group ``index`` in bar group order.

    Colour cycle is ``index // 10``. Shape 0 is a circle, then square,
    triangle, and diamond. Shape 4 is a circle again.
    """
    cycle = int(index) // len(GROUP_COLOURS)
    return MARKERS[cycle % len(MARKERS)]


def _group_style(group_names, has_groups):
    """Colours, markers, legend, notes, and paint order.

    Paint order lists row indexes. A later index is drawn later.
    """
    if not has_groups:
        seen = []
        for name in group_names:
            if name not in seen:
                seen.append(name)
        label = seen[0] if len(seen) == 1 else "samples"
        legend = [{"group": label, "colour": UNGROUPED_COLOUR, "marker": "circle"}]
        colours = [UNGROUPED_COLOUR] * len(group_names)
        markers = ["circle"] * len(group_names)
        return colours, markers, legend, "", "", list(range(len(group_names)))
    order_names = []
    buckets = {}
    for index, name in enumerate(group_names):
        if name not in buckets:
            order_names.append(name)
            buckets[name] = []
        buckets[name].append(index)
    legend = []
    colour_of = {}
    marker_of = {}
    for index, name in enumerate(order_names):
        colour = GROUP_COLOURS[index % len(GROUP_COLOURS)]
        marker = _marker_name(index)
        colour_of[name] = colour
        marker_of[name] = marker
        legend.append({"group": name, "colour": colour, "marker": marker})
    note = CYCLE_NOTE if len(order_names) > len(GROUP_COLOURS) else ""
    shape_note = SHAPE_NOTE if len(order_names) > len(GROUP_COLOURS) * len(MARKERS) else ""
    paint = []
    for name in order_names:
        paint.extend(buckets[name])
    colours = [colour_of[name] for name in group_names]
    markers = [marker_of[name] for name in group_names]
    return colours, markers, legend, note, shape_note, paint


def plan_simplex(q, iids, groups, colours, legend=None, *, k=None, has_groups=True, language="en"):
    """Geometry for one simplex figure. Does not import Pillow."""
    raw = np.asarray(q, dtype=np.float64)
    if raw.ndim != 2:
        _exit("polygon_shape", language, ndim=int(raw.ndim))
    matrix = np.array(raw, dtype=np.float64, copy=True)
    n, cols = int(matrix.shape[0]), int(matrix.shape[1])
    if k is None:
        count = cols
    else:
        count = int(k)
        if count != cols:
            _exit("polygon_k_mismatch", language, k=count, cols=cols)
    if count == 1:
        _exit("polygon_k1", language)
    if count < 2:
        _exit("polygon_columns", language, k=count)
    if iids is None or len(iids) != n:
        got = 0 if iids is None else len(iids)
        _exit("polygon_rows", language, ids=got, rows=n)
    if groups is None:
        if has_groups:
            _exit("polygon_groups", language, groups=0, rows=n)
        group_raw = [""] * n
    else:
        group_raw = list(groups)
        if len(group_raw) != n:
            _exit("polygon_groups", language, groups=len(group_raw), rows=n)
    colour_list = list(colours)
    if len(colour_list) != count:
        _exit("polygon_colours", language, k=count, got=len(colour_list))
    names = _legend_names(legend, count, language)
    iid_text = [_clean_field(iids[index], "iid", index + 1, language) for index in range(n)]
    group_text = [_clean_field(group_raw[index], "group", index + 1, language) for index in range(n)]
    for index, name in enumerate(names):
        names[index] = _clean_field(name, "legend", index + 1, language)
    basis = vertices(count)
    xy = polygon_xy(matrix)
    point_radius = POINT_R_LARGE if n > LARGE_N else POINT_R
    width = PAD_LEFT + PLOT_PX + GUTTER_PX
    point_colours, point_markers, group_legend, group_note, shape_note, paint = _group_style(
        group_text, bool(has_groups),
    )
    extra = len(_note_lines(group_note)) + len(_note_lines(shape_note))
    legend_px = PAD_TOP + (len(group_legend) + extra) * LEGEND_PITCH
    height = max(PAD_TOP + PLOT_PX + PAD_BOTTOM, legend_px + PAD_BOTTOM)
    center_x = PAD_LEFT + PLOT_PX / 2.0
    center_y = PAD_TOP + PLOT_PX / 2.0
    vertex_rows = []
    for index in range(count):
        math_x = float(basis[index, 0])
        math_y = float(basis[index, 1])
        anchor, dx, dy = _label_place(math_x, math_y)
        vertex_rows.append({
            "index": index,
            "label": names[index],
            "label_full": names[index],
            "truncated": False,
            "colour": str(colour_list[index]),
            "math_x": math_x,
            "math_y": math_y,
            "x": center_x + math_x * RADIUS_PX,
            "y": center_y - math_y * RADIUS_PX,
            "label_anchor": anchor,
            "label_dx": dx,
            "label_dy": dy,
        })
    point_rows = []
    for index in range(n):
        math_x = float(xy[index, 0])
        math_y = float(xy[index, 1])
        point_rows.append({
            "index": index,
            "iid": iid_text[index],
            "group": group_text[index],
            "math_x": math_x,
            "math_y": math_y,
            "x": center_x + math_x * RADIUS_PX,
            "y": center_y - math_y * RADIUS_PX,
            "colour": point_colours[index],
            "marker": point_markers[index],
            "radius": point_radius,
            "q": [float(value) for value in matrix[index]],
        })
    corner = CORNER_TEXT if count > 3 else ""
    return {
        "k": count,
        "width": width,
        "height": height,
        "plot": {"x": PAD_LEFT, "y": PAD_TOP, "width": PLOT_PX, "height": PLOT_PX},
        "radius_px": RADIUS_PX,
        "scale": SCALE,
        "vertex_radius": VERTEX_R,
        "point_radius": point_radius,
        "outline": OUTLINE,
        "outline_kind": "segment" if count == 2 else "polygon",
        "ink": INK,
        "opaque": True,
        "corner_text": corner,
        "many_to_one": count > 3,
        "vertices": vertex_rows,
        "points": point_rows,
        "draw_order": paint,
        "group_legend": group_legend,
        "group_note": group_note,
        "shape_note": shape_note,
        "ungrouped": not bool(has_groups),
        "colours": [str(item) for item in colour_list],
        "legend": names,
        "truncated_vertices": [],
    }


def _disc(pen, cx, cy, radius, fill):
    pen.ellipse(
        [cx - radius, cy - radius, cx + radius, cy + radius],
        fill=fill,
    )


def _marker_points(cx, cy, radius, marker):
    """Polygon vertices whose extent matches the circle diameter ``2 * radius``.

    The square side is that diameter. The diamond reaches the same
    distance on each axis. The triangle is equilateral and points up.
    Its base is that diameter, so its height is radius times sqrt(3),
    and the bounding box is centred on the point.
    """
    if marker == "square":
        return [
            (cx - radius, cy - radius),
            (cx + radius, cy - radius),
            (cx + radius, cy + radius),
            (cx - radius, cy + radius),
        ]
    if marker == "diamond":
        return [
            (cx, cy - radius),
            (cx + radius, cy),
            (cx, cy + radius),
            (cx - radius, cy),
        ]
    if marker == "triangle":
        # Equilateral. Base equals the diameter. Height is r * sqrt(3).
        # The bounding box is centred on the point, and the tip points up.
        half_w = radius
        half_h = radius * math.sqrt(3.0) / 2.0
        return [
            (cx, cy - half_h),
            (cx - half_w, cy + half_h),
            (cx + half_w, cy + half_h),
        ]
    raise ValueError("unknown marker %s" % marker)


def _paint_marker(pen, cx, cy, radius, marker, fill):
    if marker == "circle":
        _disc(pen, cx, cy, radius, fill)
        return
    pen.polygon(_marker_points(cx, cy, radius, marker), fill=fill)


def _draw(geometry):
    """Paint ``geometry`` at 2x and resize with LANCZOS. This imports Pillow."""
    from PIL import Image, ImageDraw

    from .plot_static import load_font

    scale = int(geometry["scale"])
    width = int(geometry["width"])
    height = int(geometry["height"])
    big = Image.new("RGB", (width * scale, height * scale), "white")
    pen = ImageDraw.Draw(big)
    outline = _rgb(geometry["outline"])
    verts = [(item["x"] * scale, item["y"] * scale) for item in geometry["vertices"]]
    if len(verts) == 2:
        pen.line(verts, fill=outline, width=scale)
    elif len(verts) > 2:
        pen.line(verts + [verts[0]], fill=outline, width=scale)
    for index in geometry["draw_order"]:
        point = geometry["points"][index]
        _paint_marker(
            pen,
            point["x"] * scale,
            point["y"] * scale,
            point["radius"] * scale,
            point["marker"],
            _rgb(point["colour"]),
        )
    vertex_r = float(geometry["vertex_radius"]) * scale
    for vertex in geometry["vertices"]:
        _disc(pen, vertex["x"] * scale, vertex["y"] * scale, vertex_r, _rgb(vertex["colour"]))
    font_label = load_font(13 * scale)
    font_corner = load_font(15 * scale)
    font_legend = load_font(13 * scale)
    ink = geometry["ink"]
    for vertex in geometry["vertices"]:
        pen.text(
            (
                (vertex["x"] + vertex["label_dx"]) * scale,
                (vertex["y"] + vertex["label_dy"]) * scale,
            ),
            vertex["label"],
            font=font_label,
            fill=ink,
            anchor=vertex["label_anchor"],
        )
    if geometry["corner_text"]:
        pen.text(
            (12 * scale, 10 * scale),
            geometry["corner_text"],
            font=font_corner,
            fill=ink,
            anchor="lt",
        )
    legend_x = (geometry["plot"]["x"] + geometry["plot"]["width"] + 16) * scale
    swatch = 12 * scale
    legend_radius = swatch / 2.0
    for index, item in enumerate(geometry["group_legend"]):
        top = (geometry["plot"]["y"] + index * LEGEND_PITCH) * scale
        _paint_marker(
            pen,
            legend_x + legend_radius,
            top + legend_radius,
            legend_radius,
            item["marker"],
            _rgb(item["colour"]),
        )
        pen.text(
            (legend_x + 16 * scale, top + legend_radius),
            item["group"],
            font=font_legend,
            fill=ink,
            anchor="lm",
        )
    note_row = len(geometry["group_legend"])
    for line in _note_lines(geometry["group_note"]):
        top = (geometry["plot"]["y"] + note_row * LEGEND_PITCH) * scale
        pen.text((legend_x, top), line, font=font_legend, fill=ink, anchor="lt")
        note_row += 1
    for line in _note_lines(geometry["shape_note"]):
        top = (geometry["plot"]["y"] + note_row * LEGEND_PITCH) * scale
        pen.text((legend_x, top), line, font=font_legend, fill=ink, anchor="lt")
        note_row += 1
    final = big.resize((width, height), Image.Resampling.LANCZOS)
    if final.mode != "RGB":
        final = final.convert("RGB")
    return final


def simplex(q, iids, groups, colours, legend=None, *, k=None, has_groups=True, language="en"):
    """Return ``(image, geometry)``.

    ``q`` is the aligned matrix in bar order. ``colours`` and ``legend``
    are the bar colours and legend names for that K. ``has_groups`` is
    false when the run had no groups file. Pillow is imported only while
    painting.
    """
    geometry = plan_simplex(
        q, iids, groups, colours, legend,
        k=k, has_groups=has_groups, language=language,
    )
    _fit_labels(geometry, language)
    image = _draw(geometry)
    return image, geometry


def polygon_tsv_text(geometry):
    """TSV text, including the final newline.

    Columns are ``iid``, ``group``, ``x``, ``y``, then ``q1`` .. ``qK``
    in aligned order. Coordinates and q use ``%.6f``. q is the raw row.
    """
    count = int(geometry["k"])
    header = ["iid", "group", "x", "y"]
    header.extend("q%d" % (index + 1) for index in range(count))
    lines = ["\t".join(header)]
    for point in geometry["points"]:
        fields = [
            point["iid"],
            point["group"],
            "%.6f" % point["math_x"],
            "%.6f" % point["math_y"],
        ]
        fields.extend("%.6f" % value for value in point["q"])
        lines.append("\t".join(fields))
    return "\n".join(lines) + "\n"


def write_polygon_files(outdir, image, geometry):
    """Write ``polygon_K{k}.png`` and ``polygon_K{k}.tsv``. Return the paths."""
    count = int(geometry["k"])
    png = os.path.join(outdir, "polygon_K%d.png" % count)
    tsv = os.path.join(outdir, "polygon_K%d.tsv" % count)
    image.save(png, format="PNG")
    with open(tsv, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(polygon_tsv_text(geometry))
    return png, tsv
