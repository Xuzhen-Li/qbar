"""Parent-share interval and one-parent residual test.

The interval is a percentile interval of row-resample replicates.
Endpoints use the nearest-rank rule documented on ``parent_share_ci``.

The test fits one previous column and permutes the residual. It can
write values of ``w*`` outside [0, 1]. It is not a pong split. It
ignores the constraint that a row sums to 1. It is not a likelihood
ratio from a published admixture model. ``c`` is not chosen again
inside the permutation.
"""
from __future__ import annotations

import math

import numpy as np

from .messages import text as _msg
from .report import parent_shares, split_parent_of


PARENT_SHARE_COLS = (
    "K_to",
    "new_column",
    "parent_column",
    "share",
    "ci_low",
    "ci_high",
    "alpha",
    "n_boot",
    "second_column",
    "second_share",
    "p_one_parent",
    "n_perm",
    "fraction_outside_unit_interval",
)

_FLOAT_COLS = (
    "share",
    "ci_low",
    "ci_high",
    "alpha",
    "second_share",
    "p_one_parent",
    "fraction_outside_unit_interval",
)


def check_parent_alpha(alpha, language="en"):
    """Return ``alpha`` as a float inside the open interval (0, 1)."""
    if isinstance(alpha, bool) or not isinstance(alpha, (int, float, np.floating)):
        raise SystemExit(_msg("parent_alpha_range", language, alpha=alpha))
    value = float(alpha)
    if not (0.0 < value < 1.0):
        raise SystemExit(_msg("parent_alpha_range", language, alpha=value))
    return value


def _nonneg_int(value, key, field):
    if isinstance(value, bool) or not isinstance(value, (int, np.integer)) or int(value) < 0:
        raise SystemExit(_msg(key, "en", **{field: value}))
    return int(value)


def _second_share(shares):
    """Second-largest share, lower index first when values tie.

    The returned number is that column's share. With fewer than two
    columns there is no second share.
    """
    values = np.asarray(shares, dtype=float).reshape(-1)
    if int(values.shape[0]) < 2:
        return None
    order = sorted(range(int(values.shape[0])), key=lambda c: (-float(values[c]), c))
    return float(values[order[1]])


def parent_share_ci(shares_boot, alpha=0.05):
    """Percentile interval of one parent-share series.

    ``shares_boot`` holds one share from each row-resample replicate.
    B is the number of shares. Sort them and apply the nearest-rank
    rule. Ranks are 1-based. The lower endpoint is the
    ceil(B * alpha / 2)-th smallest share. The upper endpoint is the
    ceil(B * (1 - alpha / 2))-th smallest share. For B = 100 and
    alpha = 0.05 those ranks are 3 and 98. On the shares
    0, 1, ..., 99 the endpoints are 2 and 97.

    If B * alpha / 2 < 1, both endpoints are NA. Alpha outside the
    open interval (0, 1) is an error.

    This is qbar's definition of the percentile interval. It is not a
    copied equation. ``ci_low`` and ``ci_high`` are floats, or the
    string NA. ``n_boot`` is B.
    """
    alpha = check_parent_alpha(alpha)
    values = np.asarray(shares_boot, dtype=float).reshape(-1)
    n_boot = int(values.shape[0])
    half = float(n_boot) * alpha / 2.0
    if half < 1.0:
        return {"ci_low": "NA", "ci_high": "NA", "alpha": alpha, "n_boot": n_boot}
    ordered = np.sort(values)
    low_rank = math.ceil(half)
    high_rank = math.ceil(float(n_boot) * (1.0 - alpha / 2.0))
    return {
        "ci_low": float(ordered[low_rank - 1]),
        "ci_high": float(ordered[high_rank - 1]),
        "alpha": alpha,
        "n_boot": n_boot,
    }


def _pack_one(parent_column, share, second_column, second_share, p_value,
              n_perm, n_extreme, fraction, zero_column):
    return {
        "parent_column": parent_column,
        "share": share,
        "second_column": second_column,
        "second_share": second_share,
        "p": p_value,
        "n_perm": int(n_perm),
        "n_extreme": n_extreme,
        "fraction_outside_unit_interval": fraction,
        "zero_column": bool(zero_column),
    }


def one_vs_two(q_prev, new_col, mask, n_perm, seed):
    """Residual test of one parent column against the runner-up share.

    ``c`` is the largest ``parent_shares`` column on ``mask``. A tie
    keeps the lower index. ``c`` is not chosen again inside the
    permutation. On the mask, ``a_hat = sum(w * q_c) / sum(q_c^2)`` and
    ``r = w - a_hat * q_c``. One call creates one
    ``numpy.random.default_rng(seed)`` and calls ``permutation(r)``
    ``n_perm`` times. Each permutation sets
    ``w* = a_hat * q_c + r_perm``. ``parent_shares`` of ``w*`` is
    recomputed and ``T*`` is the second-largest share. ``T`` is the
    observed second-largest share.
    ``p = (1 + count(T* >= T)) / (n_perm + 1)``.

    ``fraction_outside_unit_interval`` counts ``w*`` entries strictly
    below 0 or strictly above 1, over every permutation, and divides by
    ``n_perm * n_mask``. ``n_mask`` is the number of True mask entries.
    Rows outside the mask are not entries. Values equal to 0 or 1 are
    inside. No tolerance is applied. The fraction is not a p value.

    A new column whose masked sum is <= 0 does not draw a generator.
    ``zero_column`` is true and ``p`` is NA. ``sum(q_c^2) <= 0``, a
    previous matrix with fewer than two columns, or ``n_perm`` of 0
    also skips the draws and sets ``p`` to NA. The generator is created
    only when the loop runs. Messages from this function are English.

    The fit can produce ``w*`` outside [0, 1]. The permutation is not a
    pong split. It ignores the constraint that a row sums to 1. It is
    not a likelihood ratio from a published admixture model.
    """
    n_perm = _nonneg_int(n_perm, "parent_perm_negative", "n")
    q_prev = np.asarray(q_prev, dtype=float)
    new_col = np.asarray(new_col, dtype=float)
    if q_prev.ndim != 2 or new_col.ndim != 1 or int(q_prev.shape[0]) != int(new_col.shape[0]):
        raise SystemExit(_msg("parent_shape", "en"))
    if mask is None:
        raise SystemExit(_msg(
            "parent_mask_shape", "en", rows=int(q_prev.shape[0]), got="none",
        ))
    mask = np.asarray(mask, dtype=bool)
    if mask.ndim != 1 or int(mask.shape[0]) != int(q_prev.shape[0]):
        got = int(mask.shape[0]) if mask.ndim >= 1 else int(mask.size)
        raise SystemExit(_msg(
            "parent_mask_shape", "en", rows=int(q_prev.shape[0]), got=got,
        ))
    parent, share, second, second_share = split_parent_of(q_prev, new_col, mask)
    if parent is None:
        # Same rule as parent_shares: a masked sum <= 0 is an all-zero share vector.
        return _pack_one("NA", 0.0, "NA", "NA", "NA", n_perm, "NA", "NA", True)
    parent = int(parent)
    share = float(share)
    if second is None or second_share is None:
        return _pack_one(parent, share, "NA", "NA", "NA", n_perm, "NA", "NA", False)
    second = int(second)
    second_share = float(second_share)
    prev_m = q_prev[mask]
    w = new_col[mask]
    q_c = np.asarray(prev_m[:, parent], dtype=float)
    denom = float(np.dot(q_c, q_c))
    if denom <= 0.0 or n_perm == 0:
        return _pack_one(
            parent, share, second, second_share, "NA", n_perm, "NA", "NA", False,
        )
    seed = _nonneg_int(seed, "parent_seed_negative", "seed")
    a_hat = float(np.dot(w, q_c) / denom)
    # Permute this residual only. A later replicate starts from r again.
    r = np.array(w - a_hat * q_c, dtype=float, copy=True)
    rng = np.random.default_rng(seed)
    n_extreme = 0
    n_outside = 0
    n_mask = int(w.shape[0])
    ones = np.ones(n_mask, dtype=bool)
    for _replicate in range(n_perm):
        r_perm = rng.permutation(r)
        w_star = a_hat * q_c + r_perm
        # Strictly outside [0, 1]. Endpoints 0 and 1 stay inside.
        n_outside += int(np.count_nonzero((w_star < 0.0) | (w_star > 1.0)))
        shares_star = parent_shares(prev_m, w_star, ones)
        t_star = _second_share(shares_star)
        if float(t_star) >= second_share:
            n_extreme += 1
    fraction = float(n_outside) / float(n_perm * n_mask)
    p_value = (1.0 + float(n_extreme)) / float(n_perm + 1)
    return _pack_one(
        parent, share, second, second_share, p_value, n_perm, n_extreme, fraction, False,
    )


def _column_label(index):
    if index == "NA":
        return "NA"
    return "C%d" % (int(index) + 1)


def _resampled_parent_share(q_prev, new_col, mask, indices, column):
    """Share of one fixed column on each saved row-index vector.

    ``column`` is not chosen again. A replicate whose masked new-column
    sum is <= 0 contributes 0, which is what ``parent_shares`` returns.
    """
    q_prev = np.asarray(q_prev, dtype=float)
    new_col = np.asarray(new_col, dtype=float).reshape(-1)
    mask = np.asarray(mask, dtype=bool)
    column = int(column)
    series = np.empty(len(indices), dtype=float)
    for i, idx in enumerate(indices):
        picked = np.asarray(idx)
        shares = parent_shares(q_prev[picked], new_col[picked], mask[picked])
        series[i] = float(shares[column])
    return series


def parent_interval_rows(aligned, meta, indices, alpha, n_boot, n_perm, seed, *,
                         want_ci, want_test, language="en"):
    """One row per K step for ``parent_share_ci.tsv``.

    The new column is the last aligned column. The parent column is the
    largest share on the full-data alignment mask, lower index on a tie.
    It is not the pong split parent. The interval, when requested, uses
    ``indices`` from the bootstrap that already ran and does not align
    again. Columns for a flag that is off are NA. A new column whose
    masked sum is <= 0 writes ``zero_column`` in ``p_one_parent`` and
    NA for both the interval and the test.
    """
    if want_ci:
        got = 0 if indices is None else len(indices)
        if indices is None or got != int(n_boot):
            raise SystemExit(_msg("parent_index_count", language, n=int(n_boot), got=got))
    rows = []
    for k_to in sorted(meta):
        prev = aligned[k_to - 1]
        new = aligned[k_to]
        new_col = np.asarray(new, dtype=float)[:, -1]
        mask = meta[k_to]["mask"]
        info = one_vs_two(
            prev,
            new_col,
            mask,
            n_perm if want_test else 0,
            seed if want_test else 0,
        )
        row = {
            "K_to": int(k_to),
            "new_column": "C%d" % int(np.asarray(new).shape[1]),
            "parent_column": _column_label(info["parent_column"]),
            "share": info["share"],
            "ci_low": "NA",
            "ci_high": "NA",
            "alpha": "NA",
            "n_boot": "NA",
            "second_column": _column_label(info["second_column"]),
            "second_share": info["second_share"],
            "p_one_parent": "NA",
            "n_perm": "NA",
            "fraction_outside_unit_interval": "NA",
        }
        if info["zero_column"]:
            row["share"] = 0.0
            row["parent_column"] = "NA"
            row["second_column"] = "NA"
            row["second_share"] = "NA"
            row["p_one_parent"] = "zero_column"
            rows.append(row)
            continue
        if want_ci:
            series = _resampled_parent_share(
                prev, new_col, mask, indices, info["parent_column"],
            )
            ci = parent_share_ci(series, alpha)
            row["ci_low"] = ci["ci_low"]
            row["ci_high"] = ci["ci_high"]
            row["alpha"] = ci["alpha"]
            row["n_boot"] = ci["n_boot"]
        if want_test:
            row["p_one_parent"] = info["p"]
            row["n_perm"] = info["n_perm"]
            row["fraction_outside_unit_interval"] = info["fraction_outside_unit_interval"]
        rows.append(row)
    return rows


def _cell(column, value):
    if value == "NA" or value is None:
        return "NA"
    if column == "p_one_parent" and value == "zero_column":
        return "zero_column"
    if column in _FLOAT_COLS:
        return "%.6f" % float(value)
    return str(value)


def write_parent_share_ci(path, rows):
    """Write ``parent_share_ci.tsv``. Floats use ``%.6f``. NA is the letters NA."""
    with open(path, "w") as handle:
        handle.write("\t".join(PARENT_SHARE_COLS) + "\n")
        for row in rows:
            handle.write("\t".join(_cell(column, row[column]) for column in PARENT_SHARE_COLS) + "\n")
