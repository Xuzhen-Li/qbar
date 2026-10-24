"""Offline HTML panel.

One file. The sample rows are embedded JSON. A script in the same file
draws one bar row per K on a canvas and shows hover text for the sample
under the pointer. Nothing in the file is loaded from the network.

``panel_payload`` builds the object. ``panel_script`` is the drawing
script, with ``sampleIndexAt``, ``rowIndexAt``, ``formatQ3``,
``tooltipText``, and ``drawPanel`` as plain functions. A later editor
can call those instead of copying this file.

The positional arguments of ``write_panel_html`` are the ones named in
the feature spec. Sample ids are not among them, so ``iids`` is a
required keyword. ``bar_w``, ``bar_h``, ``title``, ``rank``, ``legend``,
and ``language`` are optional keywords. ``bar_h`` left unset is 220 when
there is one K and 120 when there are more, the same rule as the PNG.

Q values are rounded with ``float("%.6f" % value)`` and then stored as
JSON numbers. The file uses compact JSON. Non-ASCII characters are
written as JSON ``\\u`` escapes. After ``json.dumps``, ``<``, ``>``, and
``&`` in that text are replaced so a sample id cannot close the script
element.

``run`` is one string per K, parallel to ``k``. ``None`` stores an empty
string for every K. A mapping uses the K as the key. A sequence follows
sorted K.

This module does not import Pillow. The left margin is 56, the same
value as ``plot_static.BAR_LEFT``. Group edges use the same truncation
as ``span_bounds``. Column 0 is the bottom of the stack. K rows run from
low to high, top to bottom. The dendrogram is not drawn. Bar slots are
``bar_w / n`` with no extra overlap. Label placement is approximate.
"""
from __future__ import annotations

import json
import os

import numpy as np

from .messages import text as _msg
from .order import spans_of

# Same left margin and gap render() uses. Kept here so this module does
# not import the Pillow drawing code.
BAR_LEFT = 56
BAR_GAP = 12
LEGEND_ROW = 18


def round_q(value):
    """Six digits after the decimal, via ``%.6f``, then back to float."""
    return float("%.6f" % float(value))


def embed_json(payload):
    """Dump ``payload`` and escape ``<``, ``>``, and ``&``.

    ``json.dumps`` runs first with ``ensure_ascii`` true. The three
    replacements use ``\\u003c``, ``\\u003e``, and ``\\u0026``.
    """
    text = json.dumps(
        payload,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=False,
        separators=(",", ":"),
    )
    return (
        text.replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
    )


def _exit(key, language, **values):
    raise SystemExit(_msg(key, language, **values))


def _runs_for(ks, runs, language):
    if runs is None:
        return [""] * len(ks)
    if isinstance(runs, dict):
        labels = []
        for k in ks:
            if k in runs:
                item = runs[k]
            elif str(k) in runs:
                item = runs[str(k)]
            else:
                item = ""
            labels.append("" if item is None else str(item))
        return labels
    labels = ["" if item is None else str(item) for item in runs]
    if len(labels) != len(ks):
        _exit("html_runs", language, got=len(labels), n=len(ks))
    return labels


def _legend_text(aligned, groups, hexes, iids, rank, ks):
    from .api import column_owners, legend_lines

    rows = []
    owner_rank = {} if rank is None else rank
    for k in ks:
        owners = column_owners(aligned[k], iids, groups, owner_rank)
        lines = legend_lines(aligned[k], groups, owners, hexes[k])
        rows.append([text for _colour, text in lines])
    return rows


def _layout(ks, legends, spans, bar_w, bar_h, title):
    longest_label = 0
    for span in spans:
        longest_label = max(longest_label, len(span["name"]) * 8)
    n_span = len(spans)
    rotate = n_span > 12 or (n_span > 0 and bar_w / float(n_span) < longest_label + 8)
    if rotate:
        label_h = int(longest_label * 0.75) + 28
    else:
        label_h = 31
    title_h = 32 if title else 8
    longest_legend = 0
    pitches = []
    for texts in legends:
        for text in texts:
            longest_legend = max(longest_legend, len(text))
        need = 4 + len(texts) * LEGEND_ROW
        pitches.append(max(bar_h, need))
    leg_w = min(max(longest_legend * 7 + 22, 80), 420)
    width = BAR_LEFT + bar_w + BAR_GAP + leg_w + 16
    height = title_h + sum(pitches) + label_h + 12
    rows = []
    y = title_h
    for pitch in pitches:
        rows.append({
            "y": y,
            "pitch": pitch,
            "bar_y": y + (pitch - bar_h) // 2,
        })
        y += pitch
    return {
        "width": width,
        "height": height,
        "left": BAR_LEFT,
        "gap": BAR_GAP,
        "bar_w": bar_w,
        "bar_h": bar_h,
        "leg_w": leg_w,
        "title": title,
        "title_h": title_h,
        "label_h": label_h,
        "rotate_labels": rotate,
        "n": None,
        "rows": rows,
    }


def panel_payload(
    aligned, order, groups, hexes, runs=None, *,
    iids, bar_w=2200, bar_h=None, title="", rank=None, legend=None, language="en",
):
    """Return the object embedded in the HTML file.

    Keys, in order: ``iid``, ``group``, ``k``, ``run``, ``q``,
    ``column_names``, ``hex``, ``legend``, ``spans``, ``layout``.

    ``iid`` and ``group`` follow display order. ``k``, ``run``, ``q``,
    ``column_names``, ``hex``, and ``legend`` are parallel. One ``q``
    entry is a list of samples, and each sample is a list of column
    values rounded to 6 decimal places. Column 0 is the bottom of the
    stack. ``spans`` has ``name``, ``start``, ``end``, ``x0``, and
    ``x1``. ``start`` and ``end`` are a 0-based half-open interval in
    display order. ``layout.rows`` has ``y``, ``pitch``, and ``bar_y``
    for each K row.
    """
    if title is None:
        title = ""
    else:
        title = str(title)
    aligned_map = {}
    for key, value in dict(aligned).items():
        matrix = np.asarray(value, dtype=float)
        if matrix.ndim != 2:
            _exit("html_shape", language, k=int(key), rows=0, n=0)
        aligned_map[int(key)] = matrix
    ks = sorted(aligned_map)
    if not ks:
        _exit("html_empty", language)
    n = int(aligned_map[ks[0]].shape[0])
    if n < 1:
        _exit("html_rows", language, n=n, n_id=0, n_group=0)
    iid_list = [str(item) for item in iids]
    group_list = [str(item) for item in groups]
    if len(iid_list) != n or len(group_list) != n:
        _exit(
            "html_rows", language, n=n, n_id=len(iid_list), n_group=len(group_list),
        )
    for k in ks:
        matrix = aligned_map[k]
        if int(matrix.shape[0]) != n:
            _exit("html_shape", language, k=k, rows=int(matrix.shape[0]), n=n)
        if int(matrix.shape[1]) != k:
            _exit(
                "html_hex", language, k=k, cols=int(matrix.shape[1]), n_hex=k,
            )
    try:
        bar_w = int(bar_w)
    except (TypeError, ValueError):
        _exit("html_width", language, width=bar_w)
    if bar_w < 1:
        _exit("html_width", language, width=bar_w)
    if bar_h is None:
        bar_h = 220 if len(ks) == 1 else 120
    try:
        bar_h = int(bar_h)
    except (TypeError, ValueError):
        _exit("html_height", language, height=bar_h)
    if bar_h < 1:
        _exit("html_height", language, height=bar_h)
    order_idx = [int(item) for item in order]
    if sorted(order_idx) != list(range(n)):
        _exit("html_order", language, got=len(order_idx), n=n)
    colour_rows = []
    q_rows = []
    names = []
    for k in ks:
        if k not in hexes and str(k) not in hexes:
            _exit("html_missing_hex", language, k=k)
        raw_hex = hexes[k] if k in hexes else hexes[str(k)]
        colours = [str(item) for item in raw_hex]
        matrix = aligned_map[k]
        if len(colours) != int(matrix.shape[1]):
            _exit(
                "html_hex", language, k=k,
                cols=int(matrix.shape[1]), n_hex=len(colours),
            )
        colour_rows.append(colours)
        block = []
        for index in order_idx:
            block.append([round_q(matrix[index, col]) for col in range(k)])
        q_rows.append(block)
        names.append(["C%d" % (col + 1) for col in range(k)])
    if legend is None:
        legend_rows = _legend_text(
            aligned_map, group_list, {k: colour_rows[i] for i, k in enumerate(ks)},
            iid_list, rank, ks,
        )
    else:
        legend_rows = [[str(item) for item in row] for row in legend]
        if len(legend_rows) != len(ks):
            _exit("html_legend", language, got=len(legend_rows), n=len(ks))
        for k, texts in zip(ks, legend_rows):
            if len(texts) != k:
                _exit("html_legend", language, got=len(texts), n=k)
    span_rows = []
    for span in spans_of(order_idx, group_list):
        start = int(span["start"])
        end = int(span["end"])
        span_rows.append({
            "name": str(span["name"]),
            "start": start,
            "end": end,
            "x0": BAR_LEFT + int(start * bar_w / n),
            "x1": BAR_LEFT + int(end * bar_w / n),
        })
    layout = _layout(ks, legend_rows, span_rows, bar_w, bar_h, title)
    layout["n"] = n
    return {
        "iid": [iid_list[index] for index in order_idx],
        "group": [group_list[index] for index in order_idx],
        "k": ks,
        "run": _runs_for(ks, runs, language),
        "q": q_rows,
        "column_names": names,
        "hex": colour_rows,
        "legend": legend_rows,
        "spans": span_rows,
        "layout": layout,
    }


def panel_style():
    """CSS for the page. No remote font and no address."""
    return "\n".join([
        "html, body {",
        "  margin: 0;",
        "  background: #ffffff;",
        "  color: #1f2937;",
        "  font-family: sans-serif;",
        "}",
        "#qbar-canvas {",
        "  display: block;",
        "}",
        "#qbar-tip {",
        "  position: fixed;",
        "  z-index: 2;",
        "  max-width: 360px;",
        "  padding: 8px 10px;",
        "  background: #1f2937;",
        "  color: #ffffff;",
        "  font: 13px sans-serif;",
        "  line-height: 1.35;",
        "  white-space: pre;",
        "  pointer-events: none;",
        "}",
        "#qbar-tip[hidden] {",
        "  display: none;",
        "}",
    ])


def panel_script():
    """Canvas script. Functions stay at the top so a later page can reuse them.

    ``sampleIndexAt(x, width, n)`` returns the sample under a point.
    ``x`` is measured from the left edge of the bar, in CSS pixels.
    ``width`` is the bar width. The right edge is a miss.
    """
    return r"""
function sampleIndexAt(x, width, n) {
  var count = Number(n);
  var span = Number(width);
  var pos = Number(x);
  if (!(count > 0) || !(span > 0)) {
    return -1;
  }
  if (pos < 0 || pos >= span) {
    return -1;
  }
  var index = Math.floor(pos * count / span);
  if (index < 0) {
    return -1;
  }
  if (index >= count) {
    return count - 1;
  }
  return index;
}

function rowIndexAt(y, rows) {
  var pos = Number(y);
  if (!rows || !(rows.length > 0)) {
    return -1;
  }
  var i;
  for (i = 0; i < rows.length; i += 1) {
    var row = rows[i];
    if (pos >= row.y && pos < row.y + row.pitch) {
      return i;
    }
  }
  return -1;
}

function formatQ3(value) {
  var number = Number(value);
  if (number !== number || number === Infinity || number === -Infinity) {
    return "NA";
  }
  var negative = number < 0;
  var rounded = Math.round(Math.abs(number) * 1000) / 1000;
  var text = rounded.toFixed(3);
  if (negative && rounded !== 0) {
    return "-" + text;
  }
  return text;
}

function tooltipText(data, rowIndex, sampleIndex) {
  var lines = [];
  lines.push("iid: " + data.iid[sampleIndex]);
  lines.push("group: " + data.group[sampleIndex]);
  lines.push("K: " + String(data.k[rowIndex]));
  lines.push("run: " + data.run[rowIndex]);
  var names = data.column_names[rowIndex];
  var values = data.q[rowIndex][sampleIndex];
  var c;
  for (c = 0; c < values.length; c += 1) {
    lines.push(names[c] + ": " + formatQ3(values[c]));
  }
  return lines.join("\n");
}

function drawStack(ctx, x, top, height, slot, qrow, colours) {
  var total = 0;
  var bounds = [];
  var c;
  for (c = 0; c < qrow.length; c += 1) {
    total += Number(qrow[c]);
    bounds.push(total);
  }
  var prev = 0;
  for (c = 0; c < qrow.length; c += 1) {
    var lo = prev;
    var hi = bounds[c];
    prev = hi;
    if (!(hi > lo)) {
      continue;
    }
    var visLo = lo;
    var visHi = hi;
    if (visHi <= 0 || visLo >= 1) {
      continue;
    }
    if (visLo < 0) {
      visLo = 0;
    }
    if (visHi > 1) {
      visHi = 1;
    }
    if (!(visHi > visLo)) {
      continue;
    }
    var segTop = top + height - visHi * height;
    var segH = (visHi - visLo) * height;
    ctx.fillStyle = colours[c];
    ctx.fillRect(x, segTop, slot, segH);
  }
}

function drawPanel(ctx, data) {
  var layout = data.layout;
  var width = layout.width;
  var height = layout.height;
  ctx.clearRect(0, 0, width, height);
  ctx.fillStyle = "#ffffff";
  ctx.fillRect(0, 0, width, height);
  ctx.fillStyle = "#1f2937";
  ctx.font = "18px sans-serif";
  if (layout.title) {
    ctx.fillText(layout.title, layout.left, 22);
  }
  var n = data.iid.length;
  var barW = layout.bar_w;
  var barH = layout.bar_h;
  var left = layout.left;
  var slot = barW / n;
  var r;
  for (r = 0; r < data.k.length; r += 1) {
    var box = layout.rows[r];
    var colours = data.hex[r];
    var qrows = data.q[r];
    var i;
    for (i = 0; i < n; i += 1) {
      drawStack(ctx, left + i * slot, box.bar_y, barH, slot, qrows[i], colours);
    }
    ctx.fillStyle = "#1f2937";
    ctx.font = "16px sans-serif";
    ctx.fillText("K" + data.k[r], 8, box.bar_y + barH / 2);
    var lx = left + barW + layout.gap;
    var ly = box.y + 14;
    ctx.font = "13px sans-serif";
    var labels = data.legend[r];
    var c;
    for (c = 0; c < colours.length; c += 1) {
      ctx.fillStyle = colours[c];
      ctx.fillRect(lx, ly - 10, 12, 12);
      ctx.fillStyle = "#1f2937";
      ctx.fillText(labels[c], lx + 16, ly);
      ly += 18;
    }
  }
  var barTop = layout.title_h;
  var barBottom = barTop;
  for (r = 0; r < layout.rows.length; r += 1) {
    barBottom += layout.rows[r].pitch;
  }
  ctx.strokeStyle = "#94a3b8";
  ctx.lineWidth = 1;
  var s;
  for (s = 0; s < data.spans.length; s += 1) {
    var span = data.spans[s];
    if (span.start <= 0) {
      continue;
    }
    ctx.beginPath();
    ctx.moveTo(span.x0 + 0.5, barTop);
    ctx.lineTo(span.x0 + 0.5, barBottom);
    ctx.stroke();
  }
  ctx.fillStyle = "#1f2937";
  var yLab = barBottom + 16;
  if (layout.rotate_labels) {
    ctx.font = "13px sans-serif";
  } else {
    ctx.font = "15px sans-serif";
  }
  for (s = 0; s < data.spans.length; s += 1) {
    var item = data.spans[s];
    if (item.x1 - item.x0 < 14) {
      continue;
    }
    var mid = Math.floor((item.x0 + item.x1) / 2);
    if (layout.rotate_labels) {
      ctx.save();
      ctx.translate(mid, yLab);
      ctx.rotate(-Math.PI / 4);
      ctx.fillText(item.name, 0, 0);
      ctx.restore();
    } else {
      var tw = ctx.measureText(item.name).width;
      ctx.fillText(item.name, mid - tw / 2, yLab);
    }
  }
}

function prepareCanvas(canvas, data) {
  var width = data.layout.width;
  var height = data.layout.height;
  var ratio = 1;
  if (typeof window !== "undefined" && window.devicePixelRatio) {
    ratio = Number(window.devicePixelRatio);
    if (!(ratio > 0)) {
      ratio = 1;
    }
  }
  canvas.style.width = width + "px";
  canvas.style.height = height + "px";
  canvas.width = Math.max(1, Math.round(width * ratio));
  canvas.height = Math.max(1, Math.round(height * ratio));
  var ctx = canvas.getContext("2d");
  ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
  return ctx;
}

function bindHover(canvas, data, tip) {
  function hide() {
    tip.hidden = true;
    tip.textContent = "";
  }
  canvas.addEventListener("mousemove", function (event) {
    var rect = canvas.getBoundingClientRect();
    var scaleX = rect.width > 0 ? data.layout.width / rect.width : 1;
    var scaleY = rect.height > 0 ? data.layout.height / rect.height : 1;
    var x = (event.clientX - rect.left) * scaleX;
    var y = (event.clientY - rect.top) * scaleY;
    var row = rowIndexAt(y, data.layout.rows);
    var sample = -1;
    if (row >= 0) {
      sample = sampleIndexAt(x - data.layout.left, data.layout.bar_w, data.iid.length);
    }
    if (row < 0 || sample < 0) {
      hide();
      return;
    }
    tip.hidden = false;
    tip.textContent = tooltipText(data, row, sample);
    tip.style.left = (event.clientX + 12) + "px";
    tip.style.top = (event.clientY + 12) + "px";
  });
  canvas.addEventListener("mouseleave", hide);
}

function bootPanel() {
  if (typeof document === "undefined") {
    return;
  }
  var dataNode = document.getElementById("qbar-data");
  var canvas = document.getElementById("qbar-canvas");
  var tip = document.getElementById("qbar-tip");
  if (!dataNode || !canvas || !tip) {
    return;
  }
  var data = JSON.parse(dataNode.textContent);
  var ctx = prepareCanvas(canvas, data);
  drawPanel(ctx, data);
  bindHover(canvas, data, tip);
}

bootPanel();
""".strip() + "\n"


def render_panel_html(payload):
    """Return the full document. The plot title stays inside the JSON."""
    return (
        "<!DOCTYPE html>\n"
        "<html lang=\"en\">\n"
        "<head>\n"
        "<meta charset=\"utf-8\">\n"
        "<title>qbar panel</title>\n"
        "<style>\n"
        + panel_style()
        + "\n</style>\n"
        "</head>\n"
        "<body>\n"
        "<canvas id=\"qbar-canvas\" width=\"1\" height=\"1\"></canvas>\n"
        "<div id=\"qbar-tip\" hidden></div>\n"
        "<script type=\"application/json\" id=\"qbar-data\">\n"
        + embed_json(payload)
        + "\n</script>\n"
        "<script id=\"qbar-draw\">\n"
        + panel_script()
        + "</script>\n"
        "</body>\n"
        "</html>\n"
    )


def write_panel_html(
    path, aligned, order, groups, hexes, runs=None, *,
    iids, bar_w=2200, bar_h=None, title="", rank=None, legend=None, language="en",
):
    """Write one offline HTML panel. See ``panel_payload`` for the keys."""
    payload = panel_payload(
        aligned, order, groups, hexes, runs,
        iids=iids, bar_w=bar_w, bar_h=bar_h, title=title, rank=rank,
        legend=legend, language=language,
    )
    folder = os.path.dirname(os.path.abspath(path))
    if folder:
        os.makedirs(folder, exist_ok=True)
    text = render_panel_html(payload)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
