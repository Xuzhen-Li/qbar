"""Read a low-confidence precision and recall table, and score flags.

The table does not choose a cut. ``REPORT_LOW`` in ``report.py`` is
unchanged. Rows for the active align method are copied onto the end of
``align_report.txt`` only when the caller asks. ``score_matches`` counts
true positives, false positives, false negatives, and true negatives
for qbar. Precision is tp / (tp + fp). Recall is tp / (tp + fn). A zero
denominator is None in that dict. A table cell that already says NA is
copied as the letters NA.
"""
from __future__ import annotations

import csv
import io
import math
import os
import sys

import numpy as np

from .messages import text as _msg


LOW_CONFIDENCE_COLUMNS = (
    "method",
    "cut",
    "precision",
    "recall",
    "n_matches",
    "split",
)

_BLOCK_TITLE = "Low-confidence table"


def score_matches(pred_low, truth_wrong, language="en"):
    """Score low-confidence flags against matches that disagree with the truth.

    ``pred_low`` and ``truth_wrong`` are equal-length boolean sequences.
    Each entry must be a bool or a numpy bool. 0 and 1 are not accepted.
    ``language`` selects the error text and defaults to English.

    Keys are ``tp``, ``fp``, ``fn``, ``tn``, ``precision``, and ``recall``.
    Precision is tp / (tp + fp). Recall is tp / (tp + fn). Either rate is
    None when its denominator is 0.
    """
    pred = _bool_list(pred_low, language)
    truth = _bool_list(truth_wrong, language)
    if len(pred) != len(truth):
        raise SystemExit(_msg(
            "lowconf_length", language, pred=len(pred), truth=len(truth),
        ))
    tp = 0
    fp = 0
    fn = 0
    tn = 0
    for flag, wrong in zip(pred, truth):
        if flag and wrong:
            tp += 1
        elif flag and not wrong:
            fp += 1
        elif (not flag) and wrong:
            fn += 1
        else:
            tn += 1
    precision = None if tp + fp == 0 else tp / (tp + fp)
    recall = None if tp + fn == 0 else tp / (tp + fn)
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "precision": precision,
        "recall": recall,
    }


def read_low_confidence_table(path, language="en"):
    """Read a TSV of precision and recall rows.

    The header must contain ``method``, ``cut``, ``precision``, ``recall``,
    ``n_matches``, and ``split``. Extra columns are ignored. Column order
    in the file does not matter. A repeated header name is an error.
    ``precision`` and ``recall`` may be the token NA. ``cut`` must be a
    finite number. ``n_matches`` must be ASCII digits. Cells are returned
    as stripped text, not reformatted. Rows stay in file order. A leading
    UTF-8 BOM is stripped. A file that is not UTF-8 is an error.
    """
    if not os.path.isfile(path):
        raise SystemExit(_msg("lowconf_not_found", language, path=path))
    try:
        with open(path, encoding="utf-8-sig", newline="") as handle:
            raw = handle.read()
    except UnicodeDecodeError:
        raise SystemExit(_msg("lowconf_encoding", language, path=path))
    reader = csv.reader(io.StringIO(raw), delimiter="\t")
    header = None
    for parts in reader:
        if _blank_row(parts):
            continue
        header = parts
        break
    if header is None:
        raise SystemExit(_msg("lowconf_no_header", language, path=path))
    names = [cell.strip() for cell in header]
    if any(name == "" for name in names):
        raise SystemExit(_msg("lowconf_blank_column", language))
    seen = set()
    for name in names:
        if name in seen:
            raise SystemExit(_msg("lowconf_duplicate_column", language, column=name))
        seen.add(name)
    missing = [name for name in LOW_CONFIDENCE_COLUMNS if name not in seen]
    if missing:
        raise SystemExit(_msg(
            "lowconf_missing", language, columns=", ".join(missing),
        ))
    index = {name: i for i, name in enumerate(names)}
    rows = []
    data_i = 0
    for parts in reader:
        if _blank_row(parts):
            continue
        data_i += 1
        if len(parts) != len(names):
            raise SystemExit(_msg(
                "lowconf_row_width", language,
                row=data_i, got=len(parts), want=len(names),
            ))
        cells = {name: parts[index[name]].strip() for name in LOW_CONFIDENCE_COLUMNS}
        if cells["method"] == "":
            raise SystemExit(_msg("lowconf_empty_method", language, row=data_i))
        _require_finite(cells["cut"], "cut", data_i, language)
        for column in ("precision", "recall"):
            if cells[column] == "NA":
                continue
            _require_finite(cells[column], column, data_i, language)
        if not _ascii_digits(cells["n_matches"]):
            raise SystemExit(_msg(
                "lowconf_bad_number", language,
                row=data_i, column="n_matches", value=cells["n_matches"],
            ))
        rows.append(cells)
    return rows


def append_low_confidence_rows(report_path, table_rows, method, language="en"):
    """Append copied rows for ``method`` to an alignment report.

    The block starts with a blank line, then the title ``Low-confidence
    table``. The next line says the copied rows do not change the
    low-confidence cut already printed above. When ``method`` has no
    rows, a warning is written to stderr and the file is not changed.
    Returns the number of copied rows.
    """
    chosen = [row for row in table_rows if row["method"] == method]
    if not chosen:
        print(_msg("lowconf_method_missing", language, method=method), file=sys.stderr)
        return 0
    lines = [
        "",
        _BLOCK_TITLE,
        _msg("lowconf_block_note", language),
        "\t".join(LOW_CONFIDENCE_COLUMNS),
    ]
    for row in chosen:
        lines.append("\t".join(row[name] for name in LOW_CONFIDENCE_COLUMNS))
    text = "\n".join(lines) + "\n"
    with open(report_path, "a", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    return len(chosen)


def _bool_list(seq, language):
    if isinstance(seq, (str, bytes)):
        raise SystemExit(_msg("lowconf_not_bool", language, value=seq))
    try:
        items = list(seq)
    except TypeError:
        raise SystemExit(_msg("lowconf_not_bool", language, value=seq))
    out = []
    for item in items:
        if isinstance(item, (bool, np.bool_)):
            out.append(bool(item))
        else:
            raise SystemExit(_msg("lowconf_not_bool", language, value=item))
    return out


def _blank_row(parts):
    return parts == [] or all(cell.strip() == "" for cell in parts)


def _ascii_digits(text):
    return text != "" and all("0" <= ch <= "9" for ch in text)


def _require_finite(text, column, row, language):
    try:
        value = float(text)
    except ValueError:
        raise SystemExit(_msg(
            "lowconf_bad_number", language, row=row, column=column, value=text,
        ))
    if not math.isfinite(value):
        raise SystemExit(_msg(
            "lowconf_bad_number", language, row=row, column=column, value=text,
        ))
    return value
