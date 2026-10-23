"""Cluster-flow edges between aligned columns at consecutive K.

``share`` is ``parent_shares`` of the destination column. ``jaccard`` is
the member-set Jaccard from ``jaccard_matrix``. Both are qbar's own
weights. A step stores one edge per pair of columns whose weight is
strictly greater than 0. Ties are kept. A source that meets two
destinations is two edges. This module does not import Pillow.
"""
from __future__ import annotations

import os

import numpy as np

from .align import JACCARD_SETS, jaccard_matrix
from .messages import text as _msg
from .report import parent_shares


FLOW_COLUMNS = (
    "K_from",
    "col_from",
    "K_to",
    "col_to",
    "weight",
    "weight_definition",
    "method",
    "low_confidence",
)


def check_consecutive_k(aligned, language="en"):
    """Refuse a gap in K the same way ``align_qs`` does.

    Sorted keys must increase by 1. The message names ``previous + 1``.
    One K, or no K, is not a gap.
    """
    ks = sorted(aligned)
    for a, b in zip(ks, ks[1:]):
        if b != a + 1:
            raise SystemExit(_msg("k_gap", language, k=a + 1))
    return ks


def _mask_for(meta, k_to, n_rows, language):
    """Alignment mask for this step, or every row when meta has none.

    ``--no-align`` leaves ``meta`` empty. A step that alignment did run
    stores the mask the report uses, under ``meta[k_to]["mask"]``.
    """
    info = meta.get(k_to) if isinstance(meta, dict) else None
    if not isinstance(info, dict) or info.get("mask") is None:
        return np.ones(n_rows, dtype=bool)
    mask = np.asarray(info["mask"], dtype=bool)
    if mask.ndim != 1 or int(mask.shape[0]) != int(n_rows):
        got = int(mask.shape[0]) if mask.ndim >= 1 else int(mask.size)
        raise SystemExit(_msg(
            "flow_mask_shape", language, rows=int(n_rows), got=got,
        ))
    return mask


def _low_by_destination(report_rows):
    """Map ``(K_to, column label)`` to the report's low_confidence flag.

    The first row for a key wins. ``None`` means the report was not built.
    """
    if report_rows is None:
        return None
    found = {}
    for row in report_rows:
        key = (int(row["K_to"]), str(row["column"]))
        if key not in found:
            found[key] = str(row["low_confidence"])
    return found


def cluster_flow(aligned, meta, method, weight, *,
                 jaccard_set="dominant", jaccard_cut=0.5,
                 report_rows=None, language="en"):
    """Edges between consecutive aligned K.

    Parameters match the public call ``cluster_flow(aligned, meta, method,
    weight)``. ``jaccard_set`` and ``jaccard_cut`` default to the jaccard
    align method (``dominant``, ``0.5``) and are used only for weight
    ``jaccard``. ``report_rows`` are alignment-report rows. When they are
    omitted, ``low_confidence`` is NA.

    An edge's ``low_confidence`` is the destination column's flag, matched
    on ``K_to`` and the aligned label (``C1``, ``C2``, ...). Matched
    columns carry yes, no, or NA from that report. The new column's report
    flag is NA, so edges into it are NA. The source column's flag is not
    consulted.

    A destination column whose masked sum is <= 0 emits no edges, for
    either weight. That is the same cutoff as ``split_parent_of``. It
    also drops a dominant-set Jaccard that would be positive only because
    tied zeros fall on the lowest index. Any strictly positive weight is
    kept. There is no tolerance. Edges are ordered by K, then destination
    column index, then source column index.

    Each edge also carries ``dest_masked_sum``, the destination column
    summed over the rows used for that step. The figure uses it for band
    thickness. It is not a column of the TSV.
    """
    if weight not in ("share", "jaccard"):
        raise SystemExit(_msg("flow_weight_choice", language, weight=weight))
    if weight == "jaccard" and jaccard_set not in JACCARD_SETS:
        raise SystemExit(_msg("flow_jaccard_set", language, kind=jaccard_set))
    if meta is None:
        meta = {}
    ks = check_consecutive_k(aligned, language=language)
    low_map = _low_by_destination(report_rows)
    edges = []
    for k_from, k_to in zip(ks, ks[1:]):
        prev = np.asarray(aligned[k_from], dtype=float)
        new = np.asarray(aligned[k_to], dtype=float)
        if prev.ndim != 2 or new.ndim != 2:
            raise SystemExit(_msg("flow_not_matrix", language))
        if prev.shape[0] != new.shape[0]:
            raise SystemExit(_msg(
                "flow_row_count", language,
                k_from=int(k_from), k_to=int(k_to),
                prev=int(prev.shape[0]), new=int(new.shape[0]),
            ))
        n_rows = int(prev.shape[0])
        mask = _mask_for(meta, k_to, n_rows, language)
        scored = None
        if weight == "jaccard":
            scored = jaccard_matrix(prev, new, mask, jaccard_set, jaccard_cut)
        n_src = int(prev.shape[1])
        for c in range(int(new.shape[1])):
            masked_sum = float(new[mask, c].sum())
            if masked_sum <= 0.0:
                continue
            if weight == "share":
                shares = parent_shares(prev, new[:, c], mask)
            else:
                shares = scored[:, c]
            dest_label = "C%d" % (c + 1)
            if low_map is None:
                flag = "NA"
            else:
                flag = low_map.get((int(k_to), dest_label), "NA")
            for s in range(n_src):
                value = float(shares[s])
                if value <= 0.0:
                    continue
                edges.append({
                    "K_from": int(k_from),
                    "col_from": "C%d" % (s + 1),
                    "K_to": int(k_to),
                    "col_to": dest_label,
                    "weight": value,
                    "weight_definition": weight,
                    "method": method,
                    "low_confidence": flag,
                    "dest_masked_sum": masked_sum,
                })
    return edges


def write_cluster_flow_tsv(path, edges):
    """Write ``cluster_flow.tsv``. Float weights use ``%.6f``.

    The header is ``FLOW_COLUMNS``. The file is UTF-8 with LF newlines.
    """
    folder = os.path.dirname(os.path.abspath(path))
    if folder:
        os.makedirs(folder, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("\t".join(FLOW_COLUMNS) + "\n")
        for edge in edges:
            fields = [
                str(int(edge["K_from"])),
                str(edge["col_from"]),
                str(int(edge["K_to"])),
                str(edge["col_to"]),
                "%.6f" % float(edge["weight"]),
                str(edge["weight_definition"]),
                str(edge["method"]),
                str(edge.get("low_confidence", "NA")),
            ]
            handle.write("\t".join(fields) + "\n")
    return path
