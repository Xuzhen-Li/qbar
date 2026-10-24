"""Write aligned Q for CLUMPP, DISTRUCT, and pong.

``--export none`` (the default) writes nothing. ``clumpp`` writes one
indfile and one population Q file per K, plus one code-to-name file.
``pong`` writes one Q file per K, a filemap, and ind2pop. Rows follow
``order``, which is the bar order. Values are copied. They are not
divided by the row sum.

The indfile has K + 5 columns. Column 1 is 1..N in that order. Column 2
is that same integer. CLUMPP says column 2 is an integer that identifies
the individual. DISTRUCT says it is a code number. ``ids.tsv`` maps the
integer to the iid. Column 3 is the token ``1``: both manuals ignore it,
and neither quoted sentence calls it percent missing. Column 4 is the
group code. Column 5 is ``:``. The next K columns are the aligned
membership values, printed ``%.6f``.

Group code 1 is the first group in the bar. The next new group is 2, and
so on. With one group label on every row, every code is 1. The population
file has one row per code: the code with a colon, the arithmetic mean of
that group's plotted rows, and the number of those rows. The mean adds
the plotted rows from top to bottom and divides by that count.

``names.txt`` puts the same code in column 1 and the group name after it.
A space in the name is kept. An empty name is refused. A newline in a
name is refused. The name is not replaced.

``ids.tsv`` has a header ``index`` and ``iid``, then one row per plotted
sample. A space in the iid is kept. A tab or a newline in the iid is
refused. An empty iid is written as an empty field.

The pong Q file has N lines and K numbers. ``filemap.txt`` is
tab-separated: ``qbar_K<k>``, K, and the Q file name. ``ind2pop.txt`` has
one group name per line in the same order as those rows. A K of 1 is
still written. pong's manual says it does not accept K = 1, so that case
prints a warning. If the exported K values skip a value, stderr names
each missing K and the files are still written.
"""
from __future__ import annotations

import os
import sys

import numpy as np

from .messages import text as _msg

_KINDS = ("clumpp", "pong")

# CLUMPP table 4 prints (x) here. DISTRUCT's individual-Q table prints (3).
# Both manuals say the column is ignored. Neither calls it percent missing.
# The spec placeholder is this token.
_COLUMN_3 = "1"


def parse_export(value, *, language="en"):
    """Return ``clumpp`` and ``pong`` names to write, in a fixed order.

    ``none`` and ``None`` write nothing. An empty string is an error, the
    same as an empty element such as ``clumpp,``. A comma-separated subset
    may name ``clumpp``, ``pong``, or both. Spaces around commas are
    ignored. A repeated name is kept once. ``none`` mixed with another name
    is an error. Any other token is an error, and the message shows the
    value that was passed.
    """
    if value is None:
        return []
    if not isinstance(value, str):
        raise SystemExit(_msg("export_choice", language, value=value))
    text = value.strip()
    if text == "none":
        return []
    parts = [part.strip() for part in text.split(",")]
    if any(part == "" or part == "none" for part in parts):
        raise SystemExit(_msg("export_choice", language, value=value))
    unknown = [part for part in parts if part not in _KINDS]
    if unknown:
        raise SystemExit(_msg("export_choice", language, value=value))
    return [name for name in _KINDS if name in parts]


def _as_text(value):
    if isinstance(value, str):
        return value
    return None


def _check_ids(ids, order, *, language="en"):
    """Refuse an iid that cannot sit in one ``ids.tsv`` field.

    A space is kept. A tab would add a column. A newline would add a row.
    An empty iid is an empty field. The indfile does not contain the iid.
    """
    for row, index in enumerate(order, start=1):
        iid = ids[index]
        if not isinstance(iid, str):
            raise SystemExit(_msg("export_iid_text", language, row=row))
        if "\t" in iid:
            raise SystemExit(_msg("export_iid_tab", language, iid=iid))
        if "\n" in iid or "\r" in iid:
            raise SystemExit(_msg("export_iid_newline", language, row=row))


def _check_groups(groups, order, *, language="en"):
    for row, index in enumerate(order, start=1):
        name = _as_text(groups[index])
        if name is None or name == "":
            raise SystemExit(_msg("export_group_empty", language, row=row))
        if "\n" in name or "\r" in name:
            raise SystemExit(_msg("export_group_newline", language, group=name))


def check_export_labels(kinds, ids, groups, order, *, language="en"):
    """Refuse labels that cannot be written. Do this before creating files.

    An iid is checked only for ``clumpp``, because ``ids.tsv`` is the only
    export file that stores it. Group names are checked for every
    requested kind. ``ind2pop.txt`` is not part of this check.
    """
    if "clumpp" in kinds:
        _check_ids(ids, order, language=language)
    if kinds:
        _check_groups(groups, order, language=language)


def _prepare(aligned, ids, groups, order, *, language="en"):
    if isinstance(aligned, (str, bytes)) or not isinstance(aligned, dict) or len(aligned) == 0:
        kind = "empty" if isinstance(aligned, dict) and len(aligned) == 0 else type(aligned).__name__
        raise SystemExit(_msg("export_aligned", language, kind=kind))
    if isinstance(ids, (str, bytes)):
        raise SystemExit(_msg("export_ids", language, ids=len(ids), rows=0))
    matrices = {}
    n = None
    first_k = None
    for key, value in aligned.items():
        try:
            k = int(key)
        except (TypeError, ValueError):
            raise SystemExit(_msg("export_aligned", language, kind=type(key).__name__)) from None
        matrix = np.asarray(value)
        if matrix.ndim != 2 or int(matrix.shape[1]) != k or k < 1:
            cols = int(matrix.shape[1]) if matrix.ndim == 2 else 0
            raise SystemExit(_msg("export_k", language, k=k, cols=cols))
        rows = int(matrix.shape[0])
        if n is None:
            n = rows
            first_k = k
        elif rows != n:
            raise SystemExit(_msg("export_rows", language, k=k, got=rows, other=first_k, rows=n))
        matrices[k] = matrix
    if len(ids) != n:
        raise SystemExit(_msg("export_ids", language, ids=len(ids), rows=n))
    if groups is None:
        groups = ["NA"] * n
    if isinstance(groups, (str, bytes)) or len(groups) != n:
        got = len(groups) if not isinstance(groups, (str, bytes)) else 1
        raise SystemExit(_msg("export_groups", language, groups=got, rows=n))
    if order is None:
        order = list(range(n))
    try:
        got = [int(item) for item in order]
    except (TypeError, ValueError):
        raise SystemExit(_msg("export_order", language, got=len(order), rows=n)) from None
    if len(got) != n or sorted(got) != list(range(n)):
        raise SystemExit(_msg("export_order", language, got=len(got), rows=n))
    return matrices, list(ids), list(groups), got


def _group_codes(groups, order):
    """Return 1-based codes in bar order, and names in code order."""
    names = []
    index = {}
    codes = []
    for row in order:
        name = groups[row]
        if name not in index:
            index[name] = len(names) + 1
            names.append(name)
        codes.append(index[name])
    return codes, names


def _fmt(value):
    return "%.6f" % float(value)


def _plotted(matrix, order):
    return np.asarray(matrix, dtype=float)[order]


def _mean_rows(plotted, codes):
    """Arithmetic means in code order. Addition follows the plotted rows."""
    width = int(plotted.shape[1])
    buckets = {}
    seen = []
    for row, code in enumerate(codes):
        if code not in buckets:
            buckets[code] = []
            seen.append(code)
        buckets[code].append(row)
    out = []
    for code in seen:
        rows = buckets[code]
        totals = [0.0] * width
        for row in rows:
            for col in range(width):
                totals[col] += float(plotted[row, col])
        count = len(rows)
        out.append((code, [item / count for item in totals], count))
    return out


def _write_text(path, text):
    if text and not text.endswith("\n"):
        text += "\n"
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    return path


def _indfile_text(plotted, codes):
    lines = []
    for row in range(plotted.shape[0]):
        number = str(row + 1)
        fields = [
            number,
            number,
            _COLUMN_3,
            str(codes[row]),
            ":",
        ]
        fields.extend(_fmt(plotted[row, col]) for col in range(plotted.shape[1]))
        lines.append(" ".join(fields))
    return "\n".join(lines) + "\n"


def _ids_text(ids, order):
    lines = ["index\tiid"]
    for row, index in enumerate(order, start=1):
        lines.append("%d\t%s" % (row, ids[index]))
    return "\n".join(lines) + "\n"


def _pop_text(plotted, codes):
    lines = []
    for code, mean, count in _mean_rows(plotted, codes):
        fields = ["%d:" % code]
        fields.extend(_fmt(value) for value in mean)
        fields.append(str(count))
        lines.append(" ".join(fields))
    return "\n".join(lines) + "\n"


def _names_text(names):
    return "".join("%d %s\n" % (code, name) for code, name in enumerate(names, start=1))


def _q_text(plotted):
    lines = []
    for row in range(plotted.shape[0]):
        lines.append(" ".join(_fmt(plotted[row, col]) for col in range(plotted.shape[1])))
    return "\n".join(lines) + "\n"


def export_clumpp(path, aligned, ids, groups=None, order=None, *, language="en"):
    """Write CLUMPP and DISTRUCT files for the aligned matrices.

    ``path`` is the directory. ``aligned`` maps K to a matrix with K
    columns. ``ids`` has one label per input row. ``groups`` has one label
    per input row. ``None`` uses ``NA`` for every row, so column 4 is 1.
    ``order`` lists input-row indexes in bar order. ``None`` keeps the
    input order. Indfile column 2 repeats column 1. ``ids.tsv`` holds the
    iid. Returns the paths written.
    """
    matrices, ids, groups, order = _prepare(
        aligned, ids, groups, order, language=language,
    )
    _check_ids(ids, order, language=language)
    _check_groups(groups, order, language=language)
    codes, names = _group_codes(groups, order)
    os.makedirs(path, exist_ok=True)
    written = [
        _write_text(os.path.join(path, "names.txt"), _names_text(names)),
        _write_text(os.path.join(path, "ids.tsv"), _ids_text(ids, order)),
    ]
    for k in sorted(matrices):
        plotted = _plotted(matrices[k], order)
        written.append(_write_text(
            os.path.join(path, "K%d.indfile" % k),
            _indfile_text(plotted, codes),
        ))
        written.append(_write_text(
            os.path.join(path, "K%d.popq" % k),
            _pop_text(plotted, codes),
        ))
    return written


def export_pong(path, aligned, ids, groups=None, order=None, *, language="en"):
    """Write pong Q files, ``filemap.txt``, and ``ind2pop.txt``.

    ``path`` is the directory. The Q files use the aligned values in bar
    order. The filemap path is the Q file name, relative to ``path``.
    Run ids are ``qbar_K<k>``. ``ids`` is accepted so the call matches
    ``export_clumpp``; the Q files do not contain ids. A K of 1 prints a
    warning and is still written. A gap between the smallest and largest
    K prints a warning that names each missing K. Those files are still
    written. ``clumpp`` does not print that warning.
    """
    matrices, ids, groups, order = _prepare(
        aligned, ids, groups, order, language=language,
    )
    _check_groups(groups, order, language=language)
    if 1 in matrices:
        print(_msg("export_pong_k1", language, name="K1.Q"), file=sys.stderr)
    present = sorted(matrices)
    missing = [k for k in range(present[0], present[-1] + 1) if k not in matrices]
    if missing:
        print(_msg(
            "export_pong_gap", language,
            missing=", ".join(str(k) for k in missing),
        ), file=sys.stderr)
    os.makedirs(path, exist_ok=True)
    ind_lines = "".join("%s\n" % groups[index] for index in order)
    written = [_write_text(os.path.join(path, "ind2pop.txt"), ind_lines)]
    map_lines = []
    for k in sorted(matrices):
        name = "K%d.Q" % k
        plotted = _plotted(matrices[k], order)
        written.append(_write_text(os.path.join(path, name), _q_text(plotted)))
        map_lines.append("qbar_K%d\t%d\t%s" % (k, k, name))
    written.append(_write_text(os.path.join(path, "filemap.txt"), "\n".join(map_lines) + "\n"))
    return written


def write_exports(outdir, kinds, aligned, ids, groups, order, *, language="en"):
    """Write the requested export directories under ``outdir`` and return paths.

    ``clumpp`` is written before ``pong`` when both are requested. An empty
    ``kinds`` writes nothing and does not create ``export``.
    """
    paths = []
    if "clumpp" in kinds:
        paths.extend(export_clumpp(
            os.path.join(outdir, "export", "clumpp"),
            aligned, ids, groups, order, language=language,
        ))
    if "pong" in kinds:
        paths.extend(export_pong(
            os.path.join(outdir, "export", "pong"),
            aligned, ids, groups, order, language=language,
        ))
    return paths
