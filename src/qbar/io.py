"""Read Q matrices, sample ids, groups, an order file, and colour text.

``.Q`` is the default. ``.meanQ`` and ``.qopt`` are the same numeric
matrix with a different extension. An EIGENSTRAT ``.ind`` file supplies
sample ids from its first column.
"""
from __future__ import annotations

import csv
import glob
import os
import sys

import numpy as np

from .messages import text as _msg

_Q_FORMATS = ("admixture", "meanq", "qopt")
_Q_EXT = {"admixture": ".q", "meanq": ".meanq", "qopt": ".qopt"}
_Q_DIR = {
    "admixture": ("*.Q", "*.q", "dir_empty_admixture"),
    "meanq": ("*.meanQ", "*.meanq", "dir_empty_meanq"),
    "qopt": ("*.qopt", "*.QOPT", "dir_empty_qopt"),
}


def _q_format(format, *, language="en"):
    if format not in _Q_FORMATS:
        raise SystemExit(_msg("q_format", language, format=format))
    return format

def norm_hex(text, *, language="en"):
    h = text.strip()
    if not h.startswith("#"):
        h = "#" + h
    if len(h) != 7:
        raise SystemExit(_msg("color_hex", language, text=text))
    try:
        int(h[1:], 16)
    except ValueError:
        raise SystemExit(_msg("color_hex", language, text=text)) from None
    return h.lower()


def load_ids(fam, ids_path, ind=None, *, language="en"):
    chosen = []
    if fam:
        chosen.append("--fam")
    if ids_path:
        chosen.append("--ids")
    if ind:
        chosen.append("--ind")
    if len(chosen) > 1:
        flags = _msg("flag_and", language).join(chosen)
        raise SystemExit(_msg("id_sources_one", language, flags=flags))
    if not chosen:
        raise SystemExit(_msg("missing_ids", language))
    path = fam or ids_path or ind
    iids = []
    extra_n = 0
    example = None
    with open(path) as f:
        for line in f:
            parts = line.split()
            if not parts or parts[0].startswith("#"):
                continue
            if fam and len(parts) >= 2:
                iids.append(parts[1])
            else:
                # --ind keeps column 1 and does not warn. --ids still warns.
                if ids_path and len(parts) > 1:
                    extra_n += 1
                    if example is None:
                        example = line.strip()
                iids.append(parts[0])
    if not fam and extra_n:
        print(
            _msg("ids_extra", language, n=extra_n, example=example),
            file=sys.stderr,
        )
    if len(iids) != len(set(iids)):
        raise SystemExit(_msg("duplicate_sample_names", language, path=path))
    if not iids:
        raise SystemExit(_msg("empty_sample_list", language, path=path))
    return iids


def load_groups(path, iids, id_col, group_col, rest_name, *, language="en"):
    groups = [""] * len(iids)
    if not path:
        return [rest_name] * len(iids)
    with open(path, newline="") as f:
        sample = f.read(4096)
        f.seek(0)
        delim = "\t" if sample.count("\t") >= sample.count(",") else ","
        reader = csv.DictReader(f, delimiter=delim)
        if reader.fieldnames is None:
            raise SystemExit(_msg("groups_no_header", language, path=path))
        if id_col not in reader.fieldnames or group_col not in reader.fieldnames:
            raise SystemExit(
                _msg(
                    "groups_missing_column",
                    language,
                    id_col=id_col,
                    group_col=group_col,
                    columns=", ".join(reader.fieldnames),
                )
            )
        mp = {}
        for row in reader:
            mp[str(row[id_col]).strip()] = (row.get(group_col) or "").strip()
    out = []
    for iid in iids:
        g = mp.get(iid, "").strip()
        out.append(g if g else rest_name)
    return out


def _dir_q(item, first_pat, second_pat):
    first = sorted(glob.glob(os.path.join(item, first_pat)))
    hits = list(first)
    seen_real = {os.path.realpath(f) for f in first}
    for f in sorted(glob.glob(os.path.join(item, second_pat))):
        key = os.path.realpath(f)
        if key in seen_real:
            continue
        seen_real.add(key)
        hits.append(f)
    return hits


def collect_q(items, format="admixture", *, language="en"):
    format = _q_format(format, language=language)
    first_pat, second_pat, empty_key = _Q_DIR[format]
    files = []
    for item in items:
        if os.path.isdir(item):
            hits = _dir_q(item, first_pat, second_pat)
            if not hits:
                raise SystemExit(_msg(empty_key, language, path=item))
        else:
            hits = sorted(glob.glob(item))
            if not hits:
                if any(ch in item for ch in "*?["):
                    raise SystemExit(_msg("no_q_match", language, item=item))
                hits = [item]
        files.extend(hits)
    uniq = []
    seen = set()
    for f in files:
        if f not in seen:
            seen.add(f)
            uniq.append(f)
    if not uniq:
        raise SystemExit(_msg("no_q_files", language))
    return uniq


def read_q(path, format="admixture", *, language="en"):
    # admixture, meanq, and qopt share this numeric read, including trailing spaces.
    format = _q_format(format, language=language)
    if not os.path.isfile(path):
        raise SystemExit(_msg("q_not_found", language, path=path))
    try:
        q = np.loadtxt(path, dtype=float, ndmin=2)
    except ValueError as exc:
        raise SystemExit(_msg("q_not_numeric", language, path=path)) from exc
    if q.size == 0 or q.ndim != 2:
        raise SystemExit(_msg("q_not_matrix", language, path=path))
    return q


def k_of(path, q, format="admixture", *, language="en"):
    # Filename K is the digit token immediately before the extension.
    # prefix.8.Q -> 8. toy.3.meanQ -> 3. myoutfiles.qopt -> none.
    # It must equal the column count. The returned K is the column count.
    format = _q_format(format, language=language)
    base = os.path.basename(path)
    stem, ext = os.path.splitext(base)
    if ext.lower() != _Q_EXT[format]:
        raise SystemExit(_msg("bad_extension", language, path=path, format=format))
    tail = stem.rsplit(".", 1)[-1] if "." in stem else ""
    k_file = int(tail) if tail.isdigit() else None
    k_col = int(q.shape[1])
    if k_file is not None and k_file != k_col:
        raise SystemExit(_msg("filename_k", language, path=path, k_file=k_file, k_col=k_col))
    return k_col


def load_q_set(paths, format="admixture", *, language="en"):
    format = _q_format(format, language=language)
    q_by_k = {}
    src = {}
    for path in paths:
        q = read_q(path, format=format, language=language)
        k = k_of(path, q, format=format, language=language)
        if k in q_by_k:
            raise SystemExit(_msg("duplicate_k", language, k=k, path_a=src[k], path_b=path))
        q_by_k[k] = q
        src[k] = path
    return q_by_k, src


def check_shapes(q_by_k, n, *, language="en"):
    """Reject a row-count mismatch, a NaN, or a loaded value < -1e-6 or > 1+1e-4.

    The endpoints -1e-6 and 1+1e-4 are kept. Inf still fails that range check.
    A row is kept, with a warning, when abs(sum - 1) > 0.05 on the loaded floats.
    """
    for k, q in sorted(q_by_k.items()):
        if q.shape[0] != n:
            raise SystemExit(_msg("row_count", language, k=k, nrows=q.shape[0], n=n))
        if np.any(q < -1e-6) or np.any(q > 1.0 + 1e-4):
            raise SystemExit(_msg("q_out_of_range", language, k=k))
        if np.any(np.isnan(q)):
            raise SystemExit(_msg("q_nan", language, k=k))
        bad = np.where(np.abs(q.sum(axis=1) - 1.0) > 0.05)[0]
        if len(bad):
            print(_msg("row_sum_warn", language, k=k, n=len(bad)), file=sys.stderr)


def order_from_file(path, iids, *, language="en"):
    """One IID per row, or a table whose header has a column named iid.

    A header is recognised only when the first cell is not itself a sample
    and one of the cells is exactly ``iid`` (case-insensitive). ``order.tsv``
    from a previous run is such a table: rank, iid, group.
    """
    lines = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            lines.append(line.split())
    if not lines:
        raise SystemExit(_msg("order_empty", language, path=path))
    head = [cell.lower() for cell in lines[0]]
    if "iid" in head and lines[0][head.index("iid")] not in set(iids):
        col = head.index("iid")
        want = [cells[col] for cells in lines[1:] if len(cells) > col]
    else:
        want = [cells[0] for cells in lines]
    if len(want) != len(set(want)):
        raise SystemExit(_msg("order_duplicate", language, path=path))
    pos = {iid: i for i, iid in enumerate(iids)}
    missing = [x for x in want if x not in pos]
    if missing:
        raise SystemExit(_msg(
            "order_unknown_names",
            language,
            n=len(missing),
            examples=", ".join(missing[:5]),
        ))
    order = [pos[x] for x in want]
    have = set(want)
    left = [i for i, iid in enumerate(iids) if iid not in have]
    if left:
        print(_msg("order_short", language, n=len(left), n_same=len(left)), file=sys.stderr)
    order.extend(left)
    return order


def parse_colors(items, color_file, *, language="en"):
    group, col = {}, {}
    raw = list(items or [])
    if color_file:
        with open(color_file) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split()
                if len(parts) < 2:
                    raise SystemExit(_msg("color_file_line", language, line=line))
                raw.append(parts[0] + "=" + parts[1])
    for item in raw:
        if "=" not in item:
            raise SystemExit(_msg("color_syntax", language, item=item))
        key, hx = item.split("=", 1)
        key = key.strip()
        hx = norm_hex(hx, language=language)
        if key[:1] in ("C", "c") and key[1:].isdigit():
            col[int(key[1:])] = hx
        else:
            group[key] = hx
    return group, col
