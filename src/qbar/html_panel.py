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
``column_names`` replaces the default C1, C2, ... labels when it is set.

``write_editor_html`` is the offline editor. It embeds a qbar-state
object and draws the bars with ``panel_script``. The edit functions are
separate from the page controls.

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
    column_names=None,
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
    if column_names is not None:
        names = _column_name_rows(column_names, ks, language)
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


def _column_name_rows(column_names, ks, language):
    if isinstance(column_names, dict):
        seq = []
        for k in ks:
            if k in column_names:
                seq.append(column_names[k])
            elif str(k) in column_names:
                seq.append(column_names[str(k)])
            else:
                _exit("html_legend", language, got=0, n=k)
    else:
        seq = list(column_names)
    if len(seq) != len(ks):
        _exit("html_legend", language, got=len(seq), n=len(ks))
    rows = []
    for k, row in zip(ks, seq):
        labels = [str(item) for item in row]
        if len(labels) != k:
            _exit("html_legend", language, got=len(labels), n=k)
        rows.append(labels)
    return rows


def write_panel_html(
    path, aligned, order, groups, hexes, runs=None, *,
    iids, bar_w=2200, bar_h=None, title="", rank=None, legend=None, language="en",
    column_names=None,
):
    """Write one offline HTML panel. See ``panel_payload`` for the keys."""
    payload = panel_payload(
        aligned, order, groups, hexes, runs,
        iids=iids, bar_w=bar_w, bar_h=bar_h, title=title, rank=rank,
        legend=legend, language=language, column_names=column_names,
    )
    folder = os.path.dirname(os.path.abspath(path))
    if folder:
        os.makedirs(folder, exist_ok=True)
    text = render_panel_html(payload)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def panel_functions():
    """Drawing functions from ``panel_script``, without the panel boot call."""
    script = panel_script()
    suffix = "bootPanel();\n"
    if not script.endswith(suffix):
        raise RuntimeError("panel script has no boot call")
    return script[: -len(suffix)]


def editor_style():
    """CSS for the editor controls. No remote font and no address."""
    return "\n".join([
        "#qbar-editor {",
        "  padding: 12px 16px 28px;",
        "  font: 14px sans-serif;",
        "}",
        "#qbar-editor button, #qbar-editor select, #qbar-editor input {",
        "  font: 14px sans-serif;",
        "  margin: 0 8px 8px 0;",
        "}",
        "#qbar-note {",
        "  min-height: 1.2em;",
        "  color: #991b1b;",
        "}",
        "#qbar-editor p {",
        "  max-width: 760px;",
        "  line-height: 1.4;",
        "}",
    ])


def editor_script():
    """Edit functions, then the page controls.

    ``applyEdit(state, op)`` returns a new state and does not read the DOM.
    Ops are ``move``, ``reorder_groups``, ``swap``, ``rename``, and ``colour``.
    ``swap`` takes ``k``, ``i``, and ``j``. ``k`` can be omitted when the
    state has one K. A swap sets ``alignment_overridden`` to true.
    """
    return r"""
var qbarState = null;
var qbarBase = null;
var qbarView = null;

function cloneState(state) {
  return JSON.parse(JSON.stringify(state));
}

function applyEdit(state, op) {
  var next = cloneState(state);
  var kind = op.op;
  if (kind === "move") {
    moveSample(next, op.iid, op.index);
  } else if (kind === "reorder_groups") {
    reorderGroups(next, op.groups);
  } else if (kind === "swap") {
    swapColumns(next, op.k, op.i, op.j);
  } else if (kind === "rename") {
    renameColumn(next, op.k, op.column, op.name);
  } else if (kind === "colour" || kind === "color") {
    colourColumn(next, op.k, op.column, op.colour || op.color);
  } else {
    throw new Error("unknown edit");
  }
  return next;
}

function moveSample(state, iid, index) {
  var from = state.sample_order.indexOf(iid);
  if (from < 0) {
    throw new Error("unknown iid " + iid);
  }
  var group = state.sample_groups[from];
  var positions = [];
  var i;
  for (i = 0; i < state.sample_groups.length; i += 1) {
    if (state.sample_groups[i] === group) {
      positions.push(i);
    }
  }
  var local = positions.indexOf(from);
  index = Number(index);
  if (index !== index || Math.floor(index) !== index || index < 0 || index >= positions.length) {
    throw new Error("index");
  }
  var block = [];
  var b;
  for (b = 0; b < positions.length; b += 1) {
    block.push(state.sample_order[positions[b]]);
  }
  block.splice(local, 1);
  block.splice(index, 0, iid);
  for (b = 0; b < positions.length; b += 1) {
    state.sample_order[positions[b]] = block[b];
  }
}

function reorderGroups(state, groups) {
  if (!groups || groups.length !== state.group_order.length) {
    throw new Error("group order");
  }
  var seen = Object.create(null);
  var i;
  for (i = 0; i < state.group_order.length; i += 1) {
    var name = state.group_order[i];
    seen[name] = (seen[name] || 0) + 1;
  }
  for (i = 0; i < groups.length; i += 1) {
    if (!seen[groups[i]]) {
      throw new Error("group order");
    }
    seen[groups[i]] -= 1;
  }
  for (i = 0; i < state.group_order.length; i += 1) {
    if (seen[state.group_order[i]] !== 0) {
      throw new Error("group order");
    }
  }
  var byGroup = Object.create(null);
  for (i = 0; i < state.sample_order.length; i += 1) {
    var group = state.sample_groups[i];
    if (!Object.prototype.hasOwnProperty.call(byGroup, group)) {
      byGroup[group] = [];
    }
    byGroup[group].push(state.sample_order[i]);
  }
  var order = [];
  var labels = [];
  for (i = 0; i < groups.length; i += 1) {
    var members = byGroup[groups[i]] || [];
    var j;
    for (j = 0; j < members.length; j += 1) {
      order.push(members[j]);
      labels.push(groups[i]);
    }
  }
  if (order.length !== state.sample_order.length) {
    throw new Error("group order");
  }
  state.group_order = groups.slice();
  state.sample_order = order;
  state.sample_groups = labels;
}

function swapColumns(state, k, i, j) {
  var key;
  if (k === undefined || k === null || k === "") {
    if (!state.k || state.k.length !== 1) {
      throw new Error("k");
    }
    key = String(state.k[0]);
  } else {
    key = String(k);
  }
  var perm = state.swaps[key];
  var clusters = state.clusters[key];
  if (!perm || !clusters) {
    throw new Error("k");
  }
  i = Number(i);
  j = Number(j);
  if (i !== i || j !== j || Math.floor(i) !== i || Math.floor(j) !== j) {
    throw new Error("column");
  }
  if (i < 0 || j < 0 || i >= perm.length || j >= perm.length) {
    throw new Error("column");
  }
  var tmp = perm[i];
  perm[i] = perm[j];
  perm[j] = tmp;
  tmp = clusters[i];
  clusters[i] = clusters[j];
  clusters[j] = tmp;
  state.alignment_overridden = true;
}

function clusterAt(state, k, column) {
  var clusters = state.clusters[String(k)];
  column = Number(column);
  if (!clusters || column !== column || Math.floor(column) !== column) {
    throw new Error("column");
  }
  if (column < 0 || column >= clusters.length) {
    throw new Error("column");
  }
  return clusters[column];
}

function renameColumn(state, k, column, name) {
  clusterAt(state, k, column).name = String(name);
}

function colourColumn(state, k, column, colour) {
  clusterAt(state, k, column).colour = String(colour);
}

function orderTxt(state) {
  return state.sample_order.join("\n") + "\n";
}

function coloursTsv(state) {
  var lines = [];
  var i;
  var c;
  for (i = 0; i < state.k.length; i += 1) {
    var cols = state.clusters[String(state.k[i])];
    for (c = 0; c < cols.length; c += 1) {
      lines.push(cols[c].name + "\t" + cols[c].colour);
    }
  }
  return lines.join("\n") + "\n";
}

function stateJson(state) {
  var text = JSON.stringify(state, null, 2);
  if (text.charAt(text.length - 1) !== "\n") {
    text = text + "\n";
  }
  return text;
}

function buildSpans(groups, barW, left) {
  var n = groups.length;
  var spans = [];
  var start = 0;
  var j;
  for (j = 1; j <= n; j += 1) {
    if (j === n || groups[j] !== groups[start]) {
      spans.push({
        name: groups[start],
        start: start,
        end: j,
        x0: left + Math.floor(start * barW / n),
        x1: left + Math.floor(j * barW / n)
      });
      start = j;
    }
  }
  return spans;
}

function buildLayout(base, legend, spans) {
  var longestLabel = 0;
  var s;
  for (s = 0; s < spans.length; s += 1) {
    var chars = spans[s].name.length * 8;
    if (chars > longestLabel) {
      longestLabel = chars;
    }
  }
  var nSpan = spans.length;
  var rotate = nSpan > 12 || (nSpan > 0 && base.bar_w / nSpan < longestLabel + 8);
  var labelH = rotate ? Math.floor(longestLabel * 0.75) + 28 : 31;
  var titleH = base.title ? 32 : 8;
  var longestLegend = 0;
  var pitches = [];
  var r;
  for (r = 0; r < legend.length; r += 1) {
    var texts = legend[r];
    var t;
    for (t = 0; t < texts.length; t += 1) {
      if (texts[t].length > longestLegend) {
        longestLegend = texts[t].length;
      }
    }
    var need = 4 + texts.length * 18;
    pitches.push(Math.max(base.bar_h, need));
  }
  var legW = Math.min(Math.max(longestLegend * 7 + 22, 80), 420);
  var width = base.left + base.bar_w + base.gap + legW + 16;
  var height = titleH;
  for (r = 0; r < pitches.length; r += 1) {
    height += pitches[r];
  }
  height += labelH + 12;
  var rows = [];
  var y = titleH;
  for (r = 0; r < pitches.length; r += 1) {
    rows.push({
      y: y,
      pitch: pitches[r],
      bar_y: y + Math.floor((pitches[r] - base.bar_h) / 2)
    });
    y += pitches[r];
  }
  return {
    width: width,
    height: height,
    left: base.left,
    gap: base.gap,
    bar_w: base.bar_w,
    bar_h: base.bar_h,
    leg_w: legW,
    title: base.title,
    title_h: titleH,
    label_h: labelH,
    rotate_labels: rotate,
    n: null,
    rows: rows
  };
}

function viewFromState(base, state) {
  var indexOf = Object.create(null);
  var i;
  for (i = 0; i < base.iid.length; i += 1) {
    indexOf[base.iid[i]] = i;
  }
  var iid = [];
  var group = [];
  for (i = 0; i < state.sample_order.length; i += 1) {
    var id = state.sample_order[i];
    var src = indexOf[id];
    iid.push(base.iid[src]);
    group.push(base.group[src]);
  }
  var n = iid.length;
  var q = [];
  var hex = [];
  var names = [];
  var legend = [];
  var r;
  for (r = 0; r < state.k.length; r += 1) {
    var key = String(state.k[r]);
    var perm = state.swaps[key];
    var clusters = state.clusters[key];
    var rows = [];
    for (i = 0; i < n; i += 1) {
      var srcRow = indexOf[iid[i]];
      var srcQ = base.q[r][srcRow];
      var out = [];
      var c;
      for (c = 0; c < perm.length; c += 1) {
        out.push(srcQ[perm[c]]);
      }
      rows.push(out);
    }
    q.push(rows);
    var colours = [];
    var colNames = [];
    var texts = [];
    for (c = 0; c < clusters.length; c += 1) {
      colours.push(clusters[c].colour);
      colNames.push(clusters[c].name);
      texts.push(clusters[c].name + " " + base.legend_suffix[r][perm[c]]);
    }
    hex.push(colours);
    names.push(colNames);
    legend.push(texts);
  }
  var spans = buildSpans(group, base.bar_w, base.left);
  var layout = buildLayout(base, legend, spans);
  layout.n = n;
  return {
    iid: iid,
    group: group,
    k: state.k.slice(),
    run: base.run,
    q: q,
    column_names: names,
    hex: hex,
    legend: legend,
    spans: spans,
    layout: layout
  };
}

function copyOnto(target, next) {
  var key;
  var drop = [];
  for (key in target) {
    if (Object.prototype.hasOwnProperty.call(target, key)) {
      drop.push(key);
    }
  }
  var d;
  for (d = 0; d < drop.length; d += 1) {
    delete target[drop[d]];
  }
  for (key in next) {
    if (Object.prototype.hasOwnProperty.call(next, key)) {
      target[key] = next[key];
    }
  }
}

function fillSelect(select, values) {
  var current = select.value;
  while (select.options.length > 0) {
    select.remove(0);
  }
  var i;
  for (i = 0; i < values.length; i += 1) {
    var opt = document.createElement("option");
    opt.value = String(values[i]);
    opt.textContent = String(values[i]);
    select.appendChild(opt);
  }
  if (current) {
    select.value = current;
  }
}

function fillSelects() {
  fillSelect(document.getElementById("qbar-move-iid"), qbarState.sample_order);
  fillSelect(document.getElementById("qbar-group"), qbarState.group_order);
  fillSelect(document.getElementById("qbar-k"), qbarState.k);
}

function redraw() {
  var next = viewFromState(qbarBase, qbarState);
  copyOnto(qbarView, next);
  var canvas = document.getElementById("qbar-canvas");
  var ctx = prepareCanvas(canvas, qbarView);
  drawPanel(ctx, qbarView);
  fillSelects();
}

function downloadText(name, text) {
  var blob = new Blob([text], {type: "application/octet-stream"});
  var link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = name;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(link.href);
}

function runOp(op) {
  var note = document.getElementById("qbar-note");
  try {
    qbarState = applyEdit(qbarState, op);
    note.textContent = "";
    redraw();
  } catch (err) {
    note.textContent = String(err && err.message ? err.message : err);
  }
}

function moveGroup(direction) {
  var name = document.getElementById("qbar-group").value;
  var groups = qbarState.group_order.slice();
  var index = groups.indexOf(name);
  var other = index + direction;
  if (index < 0 || other < 0 || other >= groups.length) {
    return;
  }
  var tmp = groups[index];
  groups[index] = groups[other];
  groups[other] = tmp;
  runOp({op: "reorder_groups", groups: groups});
}

function bootEditor() {
  if (typeof document === "undefined") {
    return;
  }
  var stateNode = document.getElementById("qbar-state");
  var baseNode = document.getElementById("qbar-base");
  var dataNode = document.getElementById("qbar-data");
  var canvas = document.getElementById("qbar-canvas");
  var tip = document.getElementById("qbar-tip");
  if (!stateNode || !baseNode || !dataNode || !canvas || !tip) {
    return;
  }
  qbarState = JSON.parse(stateNode.textContent);
  qbarBase = JSON.parse(baseNode.textContent);
  qbarView = JSON.parse(dataNode.textContent);
  var ctx = prepareCanvas(canvas, qbarView);
  drawPanel(ctx, qbarView);
  bindHover(canvas, qbarView, tip);
  fillSelects();
  document.getElementById("qbar-move").addEventListener("click", function () {
    runOp({
      op: "move",
      iid: document.getElementById("qbar-move-iid").value,
      index: Number(document.getElementById("qbar-move-index").value)
    });
  });
  document.getElementById("qbar-group-up").addEventListener("click", function () {
    moveGroup(-1);
  });
  document.getElementById("qbar-group-down").addEventListener("click", function () {
    moveGroup(1);
  });
  document.getElementById("qbar-swap").addEventListener("click", function () {
    runOp({
      op: "swap",
      k: Number(document.getElementById("qbar-k").value),
      i: Number(document.getElementById("qbar-col-i").value),
      j: Number(document.getElementById("qbar-col-j").value)
    });
  });
  document.getElementById("qbar-rename").addEventListener("click", function () {
    runOp({
      op: "rename",
      k: Number(document.getElementById("qbar-k").value),
      column: Number(document.getElementById("qbar-col-i").value),
      name: document.getElementById("qbar-name").value
    });
  });
  document.getElementById("qbar-colour-btn").addEventListener("click", function () {
    runOp({
      op: "colour",
      k: Number(document.getElementById("qbar-k").value),
      column: Number(document.getElementById("qbar-col-i").value),
      colour: document.getElementById("qbar-colour").value
    });
  });
  document.getElementById("qbar-save-state").addEventListener("click", function () {
    downloadText("state.json", stateJson(qbarState));
  });
  document.getElementById("qbar-save-order").addEventListener("click", function () {
    downloadText("order.txt", orderTxt(qbarState));
  });
  document.getElementById("qbar-save-colours").addEventListener("click", function () {
    downloadText("colours.tsv", coloursTsv(qbarState));
  });
}

bootEditor();
""".strip() + "\n"


def build_editor_base(iids, groups, aligned, owners, ks, runs, bar_w, bar_h, title):
    """Q in input order, columns in aligned order, before a later swap."""
    from .report import column_label

    q_rows = []
    suffixes = []
    group_list = [str(item) for item in groups]
    for k in ks:
        matrix = np.asarray(aligned[k], dtype=float)
        block = []
        for index in range(int(matrix.shape[0])):
            block.append([round_q(matrix[index, col]) for col in range(int(k))])
        q_rows.append(block)
        own = owners[k]
        suffix = []
        for col in range(int(k)):
            suffix.append(column_label(own[col], matrix, group_list, col))
        suffixes.append(suffix)
    if runs is None:
        run_row = [""] * len(ks)
    else:
        run_row = ["" if item is None else str(item) for item in runs]
    return {
        "iid": [str(item) for item in iids],
        "group": group_list,
        "k": [int(k) for k in ks],
        "run": run_row,
        "q": q_rows,
        "legend_suffix": suffixes,
        "left": BAR_LEFT,
        "gap": BAR_GAP,
        "bar_w": int(bar_w),
        "bar_h": int(bar_h),
        "title": "" if title is None else str(title),
    }


def render_editor_html(payload, state, base):
    """One offline editor page. The plot title stays inside the JSON."""
    note = (
        "order.txt is one sample id per line. "
        "colours.tsv is a name, a tab, and a colour such as #rrggbb. "
        "The reader joins the name and the colour with an equals sign. "
        "A name that is C plus digits is a column colour. "
        "Any other name is a group colour. "
        "Lines run from low K to high K, and within a K from the bottom of the stack. "
        "state.json is the replay file."
    )
    controls = "\n".join([
        "<div id=\"qbar-editor\">",
        "<p>%s</p>" % note,
        "<p>",
        "<label>Sample <select id=\"qbar-move-iid\"></select></label>",
        "<label>Index in group <input id=\"qbar-move-index\" type=\"number\" min=\"0\" value=\"0\"></label>",
        "<button id=\"qbar-move\" type=\"button\">Move in group</button>",
        "</p>",
        "<p>",
        "<label>Group <select id=\"qbar-group\"></select></label>",
        "<button id=\"qbar-group-up\" type=\"button\">Group up</button>",
        "<button id=\"qbar-group-down\" type=\"button\">Group down</button>",
        "</p>",
        "<p>",
        "<label>K <select id=\"qbar-k\"></select></label>",
        "<label>Column from 0 <input id=\"qbar-col-i\" type=\"number\" min=\"0\" value=\"0\"></label>",
        "<label>Other column <input id=\"qbar-col-j\" type=\"number\" min=\"0\" value=\"1\"></label>",
        "<button id=\"qbar-swap\" type=\"button\">Swap columns</button>",
        "</p>",
        "<p>",
        "<label>Name <input id=\"qbar-name\" type=\"text\" value=\"\"></label>",
        "<button id=\"qbar-rename\" type=\"button\">Rename column</button>",
        "<label>Colour <input id=\"qbar-colour\" type=\"text\" value=\"#4470b7\"></label>",
        "<button id=\"qbar-colour-btn\" type=\"button\">Set colour</button>",
        "</p>",
        "<p>",
        "<button id=\"qbar-save-state\" type=\"button\">Download state.json</button>",
        "<button id=\"qbar-save-order\" type=\"button\">Download order.txt</button>",
        "<button id=\"qbar-save-colours\" type=\"button\">Download colours.tsv</button>",
        "</p>",
        "<p id=\"qbar-note\"></p>",
        "</div>",
    ])
    return (
        "<!DOCTYPE html>\n"
        "<html lang=\"en\">\n"
        "<head>\n"
        "<meta charset=\"utf-8\">\n"
        "<title>qbar editor</title>\n"
        "<style>\n"
        + panel_style()
        + "\n"
        + editor_style()
        + "\n</style>\n"
        "</head>\n"
        "<body>\n"
        "<canvas id=\"qbar-canvas\" width=\"1\" height=\"1\"></canvas>\n"
        "<div id=\"qbar-tip\" hidden></div>\n"
        + controls
        + "\n"
        "<script type=\"application/json\" id=\"qbar-data\">\n"
        + embed_json(payload)
        + "\n</script>\n"
        "<script type=\"application/json\" id=\"qbar-base\">\n"
        + embed_json(base)
        + "\n</script>\n"
        "<script type=\"application/json\" id=\"qbar-state\">\n"
        + embed_json(state)
        + "\n</script>\n"
        "<script id=\"qbar-draw\">\n"
        + panel_functions()
        + editor_script()
        + "</script>\n"
        "</body>\n"
        "</html>\n"
    )


def write_editor_html(path, payload, state, base):
    """Write ``editor.html``. ``payload`` is the F3 panel object."""
    folder = os.path.dirname(os.path.abspath(path))
    if folder:
        os.makedirs(folder, exist_ok=True)
    text = render_editor_html(payload, state, base)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
