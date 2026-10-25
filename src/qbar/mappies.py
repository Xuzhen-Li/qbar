"""Optional pies at sampling sites.

``pies`` places one pie per site on a white canvas. x is longitude and y
is latitude, with the same scale on both axes. That is not a projection.
The figure says so. Nothing is downloaded. A world file is not read.
Cartopy is not used.

Pillow is imported only inside ``_draw``. Planning the geometry does not
import it.

The picture is drawn at twice the final size and resized with Pillow's
LANCZOS filter. The filter is fixed. Two runs in one environment write
the same PNG bytes.

``--vector`` does not write ``map_pies.pdf`` or ``map_pies.svg``.

Mean Q is the arithmetic mean of every sample whose group equals the
site group. The bar draws every row of the aligned matrix. ``--align-mode
core``, ``--align-groups``, and the row masks used by bootstrap and
permutation change which rows match columns. They do not remove rows
from the bar, and they do not remove rows from this mean. A row kept
after the row-sum warning is included. An empty group cell has already
been replaced by ``--rest-name`` before this function sees it.

Wedge angles are ``360 * mean_q / sum(mean_q)`` when the sum is positive,
so a mean that is slightly off 1 still fills the circle. The mean stored
on the pie and in ``map_pies.tsv`` is the unscaled average. A sum of 0
draws no wedges. The first wedge starts at -90 degrees, which is 12
o'clock in Pillow (0 is 3 o'clock, and angles increase clockwise), and
later wedges follow in aligned column order.

The data box expands an axis whose span is below 1 degree to 1 degree
about its center, then extends each side by 10 percent of that span.
``--basemap-bbox`` replaces that box and is not padded. Radius is
``40 * sqrt(n / n_max)`` pixels, and at least 6. Sites that share a
longitude and a latitude keep the first pie. Each later pie is shifted
a further 4 px right (4, 8, 12 px ...).
"""
from __future__ import annotations

import math
import os
import sys

import numpy as np

from .messages import text as _msg

MAP_WIDTH = 1600
MAP_LEFT = 84
MAP_RIGHT = 340
MAP_TOP = 42
MAP_BOTTOM = 58
MAP_R_MAX = 40.0
MAP_R_MIN = 6.0
MAP_OFFSET = 4.0
MAP_SCALE = 2
MAP_PAD = 0.10
MAP_MIN_SPAN = 1.0
MAP_NOTE = "longitude, latitude, as given, no projection"
_HEADER = ("site", "latitude", "longitude", "group")


def _exit(key, language, **values):
    raise SystemExit(_msg(key, language, **values))


def require_basemap_pair(sites, image, bbox, *, language="en"):
    """Error when the image and the box are not passed together.

    Either one also requires ``--sites``. A world file is not consulted.
    """
    has_image = bool(image)
    has_bbox = bool(bbox)
    if has_image != has_bbox:
        _exit("basemap_pair", language)
    if (has_image or has_bbox) and not sites:
        _exit("basemap_needs_sites", language)


def parse_bbox(text, *, language="en"):
    """Return ``(lon_min, lat_min, lon_max, lat_max)``.

    ``text`` is four finite numbers separated by commas. The longitude
    span and the latitude span must both be positive. This is not a
    world file.
    """
    parts = [item.strip() for item in str(text).split(",")]
    if len(parts) != 4:
        _exit("basemap_bbox", language, value=text)
    values = []
    for item in parts:
        try:
            number = float(item)
        except (TypeError, ValueError):
            _exit("basemap_bbox", language, value=text)
        if not math.isfinite(number):
            _exit("basemap_bbox", language, value=text)
        values.append(number)
    lon0, lat0, lon1, lat1 = values
    if not (lon1 > lon0 and lat1 > lat0):
        _exit("basemap_bbox", language, value=text)
    return (lon0, lat0, lon1, lat1)


def _coord(site, token, kind, language):
    key = "sites_latitude" if kind == "latitude" else "sites_longitude"
    shown = "" if token is None else str(token).strip()
    try:
        value = float(shown)
    except (TypeError, ValueError):
        _exit(key, language, site=site, value=shown)
    if not math.isfinite(value):
        _exit(key, language, site=site, value=shown)
    if kind == "latitude" and (value < -90.0 or value > 90.0):
        _exit(key, language, site=site, value=shown)
    if kind == "longitude" and (value < -180.0 or value > 180.0):
        _exit(key, language, site=site, value=shown)
    return value


def _validate_rows(rows, *, language="en"):
    """Check site names, groups, and coordinates. Return new dicts."""
    if not rows:
        _exit("sites_empty", language)
    seen = {}
    by_group = {}
    out = []
    for raw in rows:
        site = str(raw.get("site", "")).strip()
        group = str(raw.get("group", "")).strip()
        if not site or not group:
            _exit("sites_blank", language, site=site or "?")
        if "\t" in site or "\t" in group or "\n" in site or "\n" in group:
            _exit("sites_blank", language, site=site)
        if site in seen:
            _exit("sites_duplicate_name", language, site=site)
        seen[site] = True
        lat_value = _coord(site, raw.get("latitude"), "latitude", language)
        lon_value = _coord(site, raw.get("longitude"), "longitude", language)
        out.append({
            "site": site,
            "latitude": lat_value,
            "longitude": lon_value,
            "group": group,
        })
        by_group.setdefault(group, []).append(site)
    for group, names in by_group.items():
        if len(names) > 1:
            _exit("sites_duplicate_group", language, group=group, sites=", ".join(names))
    return out


def read_sites(path, *, language="en"):
    """Read the site TSV. UTF-8, and a leading BOM is ignored.

    The header is ``site``, ``latitude``, ``longitude``, ``group``,
    separated by tabs. Blank lines are ignored. A repeated site name is
    an error. Two rows that name the same group are an error, and the
    message names those sites.
    """
    if not os.path.isfile(path):
        _exit("sites_missing", language, path=path)
    try:
        with open(path, encoding="utf-8-sig", newline="") as handle:
            raw = handle.read()
    except OSError:
        _exit("sites_missing", language, path=path)
    except UnicodeError:
        _exit("sites_read", language, path=path)
    lines = raw.splitlines()
    if not lines:
        _exit("sites_header", language, header="")
    header = [item.strip() for item in lines[0].split("\t")]
    if tuple(header) != _HEADER:
        _exit("sites_header", language, header=", ".join(header))
    parsed = []
    for lineno, line in enumerate(lines[1:], start=2):
        if not line.strip():
            continue
        fields = line.split("\t")
        if len(fields) != 4:
            _exit("sites_row", language, row=lineno)
        site, lat_s, lon_s, group = [item.strip() for item in fields]
        parsed.append({
            "site": site,
            "latitude": lat_s,
            "longitude": lon_s,
            "group": group,
        })
    return _validate_rows(parsed, language=language)


def _expand_span(low, high, minimum):
    span = high - low
    if span >= minimum:
        return low, high
    mid = (low + high) / 2.0
    half = minimum / 2.0
    return mid - half, mid + half


def data_bbox(rows):
    """Padded longitude and latitude box for these sites.

    An axis shorter than 1 degree is widened to 1 degree about its
    center. Each side then grows by 10 percent of that span.
    """
    lons = [row["longitude"] for row in rows]
    lats = [row["latitude"] for row in rows]
    lon0, lon1 = _expand_span(min(lons), max(lons), MAP_MIN_SPAN)
    lat0, lat1 = _expand_span(min(lats), max(lats), MAP_MIN_SPAN)
    pad_lon = MAP_PAD * (lon1 - lon0)
    pad_lat = MAP_PAD * (lat1 - lat0)
    return (lon0 - pad_lon, lat0 - pad_lat, lon1 + pad_lon, lat1 + pad_lat)


def _legend_names(legend, k):
    if legend is None:
        return ["C%d" % (index + 1) for index in range(k)]
    names = []
    for index, item in enumerate(legend):
        if isinstance(item, (tuple, list)) and len(item) >= 2:
            names.append(str(item[-1]))
        else:
            names.append(str(item))
    if len(names) != k:
        return None
    return names


def _colour_list(colours, k, language):
    if colours is None or len(colours) != k:
        got = 0 if colours is None else len(colours)
        _exit("sites_colours", language, k=k, got=got)
    out = []
    for item in colours:
        text = str(item).strip().lower()
        if not text.startswith("#"):
            text = "#" + text
        out.append(text)
    return out


def _project(lon, lat, bbox, plot):
    lon0, lat0, lon1, lat1 = bbox
    x = plot["x"] + (lon - lon0) / (lon1 - lon0) * plot["width"]
    y = plot["y"] + (lat1 - lat) / (lat1 - lat0) * plot["height"]
    return x, y


def _outside(lon, lat, bbox):
    lon0, lat0, lon1, lat1 = bbox
    return lon < lon0 or lon > lon1 or lat < lat0 or lat > lat1


def plan_pies(rows, q, groups, colours, legend, bbox=None, *, k=None, basemap=False, language="en"):
    """Return the geometry dict. Prints skip, overlap, and clip warnings.

    ``rows`` are validated site records. ``q`` is the aligned matrix at
    one K, one row per sample, in the same order as ``groups``. Samples
    are not dropped to match an alignment mask. ``bbox`` None builds the
    padded box from the sites that have samples. A skipped site does not
    move that box.
    """
    matrix = np.asarray(q, dtype=float)
    if matrix.ndim != 2:
        _exit("sites_shape", language, rows=0, got=len(groups))
    if len(groups) != matrix.shape[0]:
        _exit("sites_shape", language, rows=int(matrix.shape[0]), got=len(groups))
    if k is None:
        k = int(matrix.shape[1])
    k = int(k)
    if k != int(matrix.shape[1]):
        _exit("sites_colours", language, k=k, got=int(matrix.shape[1]))
    colour_row = _colour_list(colours, k, language)
    names = _legend_names(legend, k)
    if names is None:
        _exit("sites_colours", language, k=k, got=len(legend))
    labels = [str(item) for item in groups]
    kept = []
    for row in rows:
        idx = [i for i, label in enumerate(labels) if label == row["group"]]
        if not idx:
            print(
                _msg("sites_skip", language, site=row["site"], group=row["group"]),
                file=sys.stderr,
            )
            continue
        mean = matrix[idx].mean(axis=0)
        kept.append({
            "site": row["site"],
            "latitude": float(row["latitude"]),
            "longitude": float(row["longitude"]),
            "group": row["group"],
            "n": len(idx),
            "mean_q": [float(value) for value in mean],
        })
    if not kept:
        _exit("sites_all_skipped", language)
    if bbox is None:
        bbox = data_bbox(kept)
    n_max = max(item["n"] for item in kept)
    lon0, lat0, lon1, lat1 = bbox
    plot_w = MAP_WIDTH - MAP_LEFT - MAP_RIGHT
    plot_h = max(1, int(round(plot_w * ((lat1 - lat0) / (lon1 - lon0)))))
    height = MAP_TOP + plot_h + MAP_BOTTOM
    plot = {"x": MAP_LEFT, "y": MAP_TOP, "width": plot_w, "height": plot_h}
    buckets = {}
    key_order = []
    pies = []
    for item in kept:
        x, y = _project(item["longitude"], item["latitude"], bbox, plot)
        total = float(np.sum(item["mean_q"]))
        if total > 0.0:
            angles = [360.0 * value / total for value in item["mean_q"]]
        else:
            angles = [0.0 for _ in item["mean_q"]]
        cursor = -90.0
        wedges = []
        for angle, colour in zip(angles, colour_row):
            end = cursor + angle
            wedges.append({"start": cursor, "end": end, "colour": colour})
            cursor = end
        radius = MAP_R_MAX * math.sqrt(item["n"] / float(n_max))
        if radius < MAP_R_MIN:
            radius = MAP_R_MIN
        pie = {
            "site": item["site"],
            "latitude": item["latitude"],
            "longitude": item["longitude"],
            "group": item["group"],
            "x": x,
            "y": y,
            "radius": radius,
            "n": item["n"],
            "mean_q": item["mean_q"],
            "shift_px": 0.0,
            "wedges": wedges,
        }
        pies.append(pie)
        key = (item["latitude"], item["longitude"])
        if key not in buckets:
            buckets[key] = []
            key_order.append(key)
        buckets[key].append(pie)
    for key in key_order:
        group = buckets[key]
        if len(group) < 2:
            continue
        for index, pie in enumerate(group):
            pie["shift_px"] = index * MAP_OFFSET
            pie["x"] = pie["x"] + pie["shift_px"]
        print(
            _msg(
                "sites_same_xy",
                language,
                sites=", ".join(pie["site"] for pie in group),
            ),
            file=sys.stderr,
        )
    if basemap:
        for pie in pies:
            if _outside(pie["longitude"], pie["latitude"], bbox):
                print(
                    _msg("sites_outside", language, site=pie["site"]),
                    file=sys.stderr,
                )
    return {
        "width": MAP_WIDTH,
        "height": height,
        "k": k,
        "bbox": [float(lon0), float(lat0), float(lon1), float(lat1)],
        "colours": colour_row,
        "legend": names,
        "note": MAP_NOTE,
        "basemap": bool(basemap),
        "plot": plot,
        "pies": pies,
    }


def _rgb(colour):
    text = colour.lstrip("#")
    return (
        int(text[0:2], 16),
        int(text[2:4], 16),
        int(text[4:6], 16),
    )


def _ticks(low, high):
    span = high - low
    if span <= 0.0:
        return [low]
    raw = span / 4.0
    mag = 10.0 ** math.floor(math.log10(raw))
    step = mag
    for factor in (1.0, 2.0, 2.5, 5.0, 10.0):
        if factor * mag >= raw - 1e-12:
            step = factor * mag
            break
    start = math.ceil((low / step) - 1e-9) * step
    ticks = []
    value = start
    guard = 0
    while value <= high + step * 1e-6 and guard < 12:
        if value >= low - step * 1e-6:
            ticks.append(value)
        value += step
        guard += 1
    if not ticks:
        return [low, high]
    return ticks


def _tick_decimals(step):
    text = "%.10f" % step
    if "." not in text:
        return 0
    frac = text.rstrip("0").split(".", 1)[1]
    return len(frac)


def _draw(geometry, basemap_image, *, language="en"):
    """Paint ``geometry`` and return an RGB image. This imports Pillow."""
    from PIL import Image, ImageChops, ImageDraw

    from .plot_static import load_font

    scale = MAP_SCALE
    width = int(geometry["width"])
    height = int(geometry["height"])
    plot = geometry["plot"]
    big = Image.new("RGB", (width * scale, height * scale), "white")
    x0 = int(plot["x"] * scale)
    y0 = int(plot["y"] * scale)
    x1 = int((plot["x"] + plot["width"]) * scale)
    y1 = int((plot["y"] + plot["height"]) * scale)
    if basemap_image:
        if not os.path.isfile(basemap_image):
            _exit("basemap_missing", language, path=basemap_image)
        try:
            with Image.open(basemap_image) as source:
                rgba = source.convert("RGBA")
                plate = Image.new("RGB", rgba.size, "white")
                plate.paste(rgba, mask=rgba.getchannel("A"))
                stretched = plate.resize((x1 - x0, y1 - y0), Image.Resampling.LANCZOS)
        except OSError:
            _exit("basemap_read", language, path=basemap_image)
        big.paste(stretched, (x0, y0))
    overlay = Image.new("RGBA", big.size, (0, 0, 0, 0))
    ink = (31, 41, 55, 255)
    draw = ImageDraw.Draw(overlay)
    for pie in geometry["pies"]:
        cx = pie["x"] * scale
        cy = pie["y"] * scale
        radius = pie["radius"] * scale
        box = [cx - radius, cy - radius, cx + radius, cy + radius]
        for wedge in pie["wedges"]:
            sweep = wedge["end"] - wedge["start"]
            if sweep <= 1e-6:
                continue
            fill = _rgb(wedge["colour"]) + (255,)
            if sweep >= 359.999:
                draw.ellipse(box, fill=fill)
            else:
                draw.pieslice(box, wedge["start"], wedge["end"], fill=fill)
        draw.ellipse(box, outline=ink)
    mask = Image.new("L", big.size, 0)
    ImageDraw.Draw(mask).rectangle([x0, y0, x1 - 1, y1 - 1], fill=255)
    alpha = ImageChops.multiply(overlay.getchannel("A"), mask)
    overlay.putalpha(alpha)
    canvas = Image.alpha_composite(big.convert("RGBA"), overlay).convert("RGB")
    pen = ImageDraw.Draw(canvas)
    frame = (31, 41, 55)
    pen.rectangle([x0, y0, x1 - 1, y1 - 1], outline=frame)
    font_note = load_font(14 * scale)
    font_tick = load_font(12 * scale)
    font_site = load_font(13 * scale)
    font_legend = load_font(13 * scale)
    pen.text((x0, 8 * scale), geometry["note"], font=font_note, fill=frame)
    lon0, lat0, lon1, lat1 = geometry["bbox"]
    lon_ticks = _ticks(lon0, lon1)
    lat_ticks = _ticks(lat0, lat1)
    lon_fmt = "%." + str(_tick_decimals(_tick_step(lon_ticks))) + "f"
    lat_fmt = "%." + str(_tick_decimals(_tick_step(lat_ticks))) + "f"
    for value in lon_ticks:
        px = x0 + (value - lon0) / (lon1 - lon0) * (x1 - x0)
        pen.line([(px, y1), (px, y1 + 6 * scale)], fill=frame)
        pen.text((px, y1 + 8 * scale), lon_fmt % value, font=font_tick, fill=frame, anchor="mt")
    pen.text(
        ((x0 + x1) / 2.0, height * scale - 8 * scale),
        "longitude",
        font=font_tick,
        fill=frame,
        anchor="mb",
    )
    for value in lat_ticks:
        py = y0 + (lat1 - value) / (lat1 - lat0) * (y1 - y0)
        pen.line([(x0 - 6 * scale, py), (x0, py)], fill=frame)
        pen.text((x0 - 8 * scale, py), lat_fmt % value, font=font_tick, fill=frame, anchor="rm")
    pen.text((8 * scale, y0), "latitude", font=font_tick, fill=frame, anchor="lt")
    legend_x = x1 + 16 * scale
    for index, (colour, label) in enumerate(zip(geometry["colours"], geometry["legend"])):
        ly = y0 + index * 22 * scale
        side = 12 * scale
        pen.rectangle([legend_x, ly, legend_x + side, ly + side], fill=_rgb(colour))
        pen.text(
            (legend_x + 16 * scale, ly + side / 2.0),
            label,
            font=font_legend,
            fill=frame,
            anchor="lm",
        )
    for pie in geometry["pies"]:
        pen.text(
            ((pie["x"] + pie["radius"] + 4.0) * scale, pie["y"] * scale),
            pie["site"],
            font=font_site,
            fill=frame,
            anchor="lm",
        )
    final = canvas.resize((width, height), Image.Resampling.LANCZOS)
    if final.mode != "RGB":
        final = final.convert("RGB")
    return final


def _tick_step(ticks):
    if len(ticks) >= 2:
        return abs(ticks[1] - ticks[0])
    return 1.0


def pies(sites, q, groups, colours, legend=None, *, k=None, basemap_image=None, bbox=None, language="en"):
    """Return ``(image, geometry)`` for these sites.

    ``sites`` is a TSV path or a list of records with ``site``,
    ``latitude``, ``longitude``, and ``group``. ``colours`` and
    ``legend`` are the aligned column colours and the bar legend names.
    ``bbox`` is the basemap box. Without it, the box is the padded data
    extent. ``basemap_image`` is stretched to that box.
    """
    rows = read_sites(sites, language=language) if isinstance(sites, (str, os.PathLike)) else _validate_rows(sites, language=language)
    use_basemap = basemap_image is not None or bbox is not None
    box = None
    if use_basemap:
        require_basemap_pair(True, basemap_image, bbox, language=language)
        if isinstance(bbox, (str, os.PathLike)):
            box = parse_bbox(bbox, language=language)
        else:
            box = parse_bbox(",".join(str(item) for item in bbox), language=language)
        if basemap_image and not os.path.isfile(basemap_image):
            _exit("basemap_missing", language, path=basemap_image)
    geometry = plan_pies(
        rows, q, groups, colours, legend, box,
        k=k, basemap=use_basemap, language=language,
    )
    image = _draw(geometry, basemap_image if use_basemap else None, language=language)
    return image, geometry


def map_tsv_text(geometry):
    """TSV text for ``map_pies.tsv``, including the final newline.

    Columns are site, latitude, longitude, group, n, K, then ``C1`` ..
    ``CK`` in aligned column order. Mean Q uses ``%.6f``. ``C1`` is the
    first aligned column, the same order as the bar. A renamed legend
    stays on the figure. It does not rename these headers.
    """
    k = int(geometry["k"])
    header = ["site", "latitude", "longitude", "group", "n", "K"]
    header.extend("C%d" % (index + 1) for index in range(k))
    lines = ["\t".join(header)]
    for pie in geometry["pies"]:
        fields = [
            pie["site"],
            "%.6f" % pie["latitude"],
            "%.6f" % pie["longitude"],
            pie["group"],
            str(int(pie["n"])),
            str(k),
        ]
        fields.extend("%.6f" % value for value in pie["mean_q"])
        lines.append("\t".join(fields))
    return "\n".join(lines) + "\n"


def write_map_files(outdir, image, geometry):
    """Write ``map_pies.png`` and ``map_pies.tsv``. Return the two paths."""
    png = os.path.join(outdir, "map_pies.png")
    tsv = os.path.join(outdir, "map_pies.tsv")
    image.save(png, format="PNG")
    text = map_tsv_text(geometry)
    with open(tsv, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    return png, tsv
