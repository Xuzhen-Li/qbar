"""Resample individuals and count how often a column match returns.

Q values stay fixed. Each replicate draws one row-index vector with
``numpy.random.default_rng(seed).integers(0, n, size=n)`` and uses that
same vector at every K. The selected align method then runs again from
the lowest K upward, with the same anchor and mask rules as ``align_qs``.

``support`` is ``n_same / n_boot``. It is a resample frequency of the
match. It is not a probability that a cluster is real, and it is not a
bootstrap of ADMIXTURE.

``match_support.tsv`` prints ``support`` with ``%.6f``. Further columns,
if a later summary needs them, are appended after ``n_empty_mask``.
When a row carries ``n_perm``, the writer appends ``n_perm``,
``n_extreme``, ``p``, ``null``, and ``zero_column``. ``p`` uses
``%.6f``. ``zero_column`` is written as ``yes`` or ``no``.
"""
from __future__ import annotations

import numpy as np

from .align import align_qs
from .messages import text as _msg

# Fixed left-to-right order. Later fields are appended after these.
MATCH_SUPPORT_COLS = (
    "K_to",
    "aligned_column",
    "raw_column",
    "n_boot",
    "n_same",
    "support",
    "seed",
    "method",
    "n_empty_mask",
)

# Appended only when a row has n_perm. Absent rows keep the ST1 header.
PERM_SUPPORT_COLS = (
    "n_perm",
    "n_extreme",
    "p",
    "null",
    "zero_column",
)


def _nonneg_int(value, key, language, field):
    if isinstance(value, bool) or not isinstance(value, (int, np.integer)) or int(value) < 0:
        raise SystemExit(_msg(key, language, **{field: value}))
    return int(value)


def _exit_text(exc):
    if isinstance(exc.code, str):
        return exc.code
    if exc.code is None:
        return ""
    return str(exc.code)


def _is_empty_mask(detail, language):
    return detail in (
        _msg("align_empty", language),
        _msg("align_empty_check", language),
    )


def _row_count(q_by_k, language):
    ks = sorted(q_by_k)
    counts = [int(np.asarray(q_by_k[k]).shape[0]) for k in ks]
    if not counts or any(item != counts[0] for item in counts):
        raise SystemExit(_msg("bootstrap_row_count", language))
    if counts[0] < 1:
        raise SystemExit(_msg("bootstrap_row_count", language))
    return ks, counts[0]


def write_match_support(path, rows):
    """Write ``match_support.tsv``. ``support`` and ``p`` use ``%.6f``.

    Rows without ``n_perm`` keep the ST1 header. ``NA`` is written as the
    letters NA. ``zero_column`` is ``yes`` or ``no``.
    """
    columns = list(MATCH_SUPPORT_COLS)
    if rows and "n_perm" in rows[0]:
        columns.extend(PERM_SUPPORT_COLS)
    with open(path, "w") as handle:
        handle.write("\t".join(columns) + "\n")
        for row in rows:
            cells = []
            for col in columns:
                value = row[col]
                if col in ("support", "p") and value != "NA":
                    cells.append("%.6f" % float(value))
                elif col == "zero_column":
                    cells.append("yes" if value is True or value == "yes" else "no")
                else:
                    cells.append(str(value))
            handle.write("\t".join(cells) + "\n")


def bootstrap_support(q_by_k, method, n_boot, seed, mask=None, *,
                      groups=None, anchor="", align_mode="all", align_groups=None,
                      qmax=0.75, jaccard_set="dominant", jaccard_cut=0.5,
                      language="en"):
    """Return one dict per aligned column at each K to K+1 step.

    ``mask``, when given, is a boolean vector of length N. It is combined
    with the align-mode mask. ``None`` uses only the align-mode rules.
    ``n_boot`` of 0 returns an empty list and does not draw a seed.
    A replicate whose mask is empty increments ``n_empty_mask`` and is
    not counted in ``n_same``. Any other qbar error inside a replicate
    stops the run.
    """
    n_boot = _nonneg_int(n_boot, "bootstrap_negative", language, "n")
    if n_boot == 0:
        return []
    seed = _nonneg_int(seed, "bootstrap_seed_negative", language, "seed")
    ks, n = _row_count(q_by_k, language)
    if len(ks) < 2:
        return []
    if groups is None:
        groups = ["NA"] * n
    else:
        groups = list(groups)
    if len(groups) != n:
        raise SystemExit(_msg("bootstrap_group_rows", language, rows=n, got=len(groups)))
    if align_groups is None:
        align_groups = []
    else:
        align_groups = list(align_groups)
    anchor = "" if anchor is None else str(anchor).strip()
    base_mask = None
    if mask is not None:
        base_mask = np.asarray(mask, dtype=bool)
        if base_mask.ndim != 1 or int(base_mask.shape[0]) != n:
            got = int(base_mask.shape[0]) if base_mask.ndim >= 1 else int(base_mask.size)
            raise SystemExit(_msg("bootstrap_mask_shape", language, rows=n, got=got))

    def _align(matrices, group_list, row_mask):
        # warn=False: the full-data run already printed Pearson warnings.
        return align_qs(
            matrices, group_list, anchor, align_mode, align_groups, qmax, True, method,
            jaccard_set, jaccard_cut, language=language, warn=False, row_mask=row_mask,
        )

    _aligned, ref_perm, _meta = _align(q_by_k, groups, base_mask)
    step_ks = ks[1:]
    n_same = {k: [0] * len(ref_perm[k]) for k in step_ks}
    n_empty = 0
    rng = np.random.default_rng(seed)
    for replicate in range(n_boot):
        # One draw. Every K in this replicate uses these row positions.
        idx = rng.integers(0, n, size=n)
        q_b = {k: np.asarray(q_by_k[k], dtype=float)[idx] for k in ks}
        groups_b = [groups[int(i)] for i in idx]
        row_mask = None if base_mask is None else base_mask[idx]
        try:
            _aligned_b, perm_b, _meta_b = _align(q_b, groups_b, row_mask)
        except SystemExit as exc:
            detail = _exit_text(exc)
            if _is_empty_mask(detail, language):
                n_empty += 1
                continue
            raise SystemExit(_msg(
                "bootstrap_replicate_failed", language, n=replicate + 1, detail=detail,
            )) from None
        for k in step_ks:
            for c in range(len(ref_perm[k])):
                if int(perm_b[k][c]) == int(ref_perm[k][c]):
                    n_same[k][c] += 1
    rows = []
    for k in step_ks:
        for c, raw in enumerate(ref_perm[k]):
            same = int(n_same[k][c])
            rows.append({
                "K_to": int(k),
                "aligned_column": "C%d" % (c + 1),
                "raw_column": int(raw) + 1,
                "n_boot": int(n_boot),
                "n_same": same,
                "support": float(same) / float(n_boot),
                "seed": int(seed),
                "method": method,
                "n_empty_mask": int(n_empty),
            })
    return rows
