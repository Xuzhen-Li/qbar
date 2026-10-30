"""Permutation p value for one column match.

qbar's own definition, with the observed statistic included:

    p = (1 + count(T* >= T)) / (n_perm + 1)

Ties count as extreme. ``n_extreme`` is that count. It does not include
the leading 1. The null name is always returned.

``rows``, the null the documentation leads with. Permute the row order
of the whole K+1 matrix with ``numpy.random.default_rng(seed)``. Each
row stays a composition. Rerun the matcher for this one K step, not the
whole chain, with the same mask and align-mode rules. ``q_prev`` is the
already aligned previous matrix, so the anchor is already applied and
this function does not call ``anchor_perm``. T is the unrounded score
``match_next`` returns for that aligned old column. Greedy and
hungarian use Pearson of the paired columns, and a constant column has
Pearson 0. Pong uses ``pong_sim`` of the two columns, and a split
parent uses ``pong_sim`` of the old column and the sum of the two child
columns. Jaccard uses the member sets, and an empty union is 0.
clumpp-full, clumpp-greedy, clumpp-largek, and clumppling-ilp use
column G' of the assigned pair. The raw index is not T. The leftover
slot has no score, so its ``p`` and ``n_extreme`` are ``NA``. A small
p means that score is in the upper tail of the shuffled scores. It
does not mean the index is the true ancestry label.

``column``. Permute the entries of the matched new column across
individuals. Other columns stay put. Do not re-solve the assignment.
T is that column's similarity to its matched old column. Pearson for
greedy, hungarian, clumpp-full, clumpp-greedy, clumpp-largek, and
clumppling-ilp. ``pong_sim`` for pong. Jaccard for jaccard. The four
clumpp and clumppling methods store column G' on the alignment. This
statistic uses Pearson for them, the same column similarity their
same-K replicate pairs use. The shuffle breaks the constraint that a
row sums to 1. It does not test a demographic model. It does not test
that a different column would have scored higher.

``column`` is the 0-based aligned index. A leftover column has no
matched old column, so under null ``column`` its ``p`` and
``n_extreme`` are ``NA``. Under null ``rows`` the leftover slot also
has no score, so its ``p`` and ``n_extreme`` are ``NA``.

An all-zero matched new column, or an all-zero paired old column, sets
``zero_column`` and the p value is still computed when T is defined.
``n_perm`` of 0 returns ``p`` as ``NA`` and does not draw a seed.
"""
from __future__ import annotations

import numpy as np

from .align import col_pearson, core_mask, match_next, member_sets, pong_sim
from .messages import text as _msg


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


def _all_zero(column):
    values = np.asarray(column, dtype=float).reshape(-1)
    if values.size == 0:
        return False
    return bool(np.all(values == 0.0))


def _alignment_mask(q_prev, q_new, groups, align_mode, align_groups, qmax, row_mask, language):
    """Same mask rules as one step of ``align_qs``."""
    if align_mode == "core":
        if not align_groups:
            raise SystemExit(_msg("core_needs_groups", language))
        mask = core_mask(q_prev, q_new, groups, align_groups, qmax, language=language)
    else:
        if align_groups:
            mask = np.array([item in set(align_groups) for item in groups])
        else:
            mask = np.ones(len(groups), dtype=bool)
        if not mask.any():
            raise SystemExit(_msg("align_empty", language))
    if row_mask is not None:
        extra = np.asarray(row_mask, dtype=bool)
        if extra.ndim != 1 or extra.shape[0] != mask.shape[0]:
            got = int(extra.shape[0]) if extra.ndim >= 1 else int(extra.size)
            raise SystemExit(_msg(
                "perm_mask_shape", language, rows=int(mask.shape[0]), got=got,
            ))
        mask = mask & extra
        if not mask.any():
            raise SystemExit(_msg("align_empty", language))
    return mask


def _matched_perm(q_prev, q_new, mask, method, jaccard_set, jaccard_cut, language):
    perm, _scores = _matched_assignment(
        q_prev, q_new, mask, method, jaccard_set, jaccard_cut, language,
    )
    return perm


def _matched_assignment(q_prev, q_new, mask, method, jaccard_set, jaccard_cut, language):
    """Raw-column order and the unrounded scores ``match_next`` returns.

    The last score is ``None``. That slot is the leftover column.
    """
    result = match_next(
        q_prev, q_new, mask, method, jaccard_set, jaccard_cut, language=language,
    )
    perm = [int(item) for item in result[0]]
    scores = [None if item is None else float(item) for item in result[1]]
    return perm, scores


def _pair_similarity(q_prev, q_new, old_c, new_j, mask, method, jaccard_set, jaccard_cut):
    """Similarity of one aligned old column and one raw new column.

    Pearson for every method except pong and jaccard. pong uses
    ``pong_sim`` of the two columns, not the merged score from the
    split search. Jaccard uses the same member sets as the matcher.
    """
    if method == "pong":
        return pong_sim(q_prev[mask, old_c], q_new[mask, new_j])
    if method == "jaccard":
        left = member_sets(q_prev, mask, jaccard_set, jaccard_cut)
        right = member_sets(q_new, mask, jaccard_set, jaccard_cut)
        both = left[:, old_c] | right[:, new_j]
        union = int(np.count_nonzero(both))
        if union == 0:
            return 0.0
        return float(np.count_nonzero(left[:, old_c] & right[:, new_j])) / float(union)
    return col_pearson(q_prev[mask, old_c], q_new[mask, new_j])


def _prepare(q_prev, q_new, method, n_perm, seed, null, *,
             mask, groups, align_mode, align_groups, qmax,
             jaccard_set, jaccard_cut, language):
    n_perm = _nonneg_int(n_perm, "perm_negative", language, "n")
    q_prev = np.asarray(q_prev, dtype=float)
    q_new = np.asarray(q_new, dtype=float)
    if q_prev.ndim != 2 or q_new.ndim != 2:
        raise SystemExit(_msg("perm_not_matrix", language))
    if int(q_prev.shape[0]) != int(q_new.shape[0]):
        raise SystemExit(_msg(
            "perm_row_count", language,
            prev=int(q_prev.shape[0]), new=int(q_new.shape[0]),
        ))
    if int(q_new.shape[1]) != int(q_prev.shape[1]) + 1:
        raise SystemExit(_msg("k_columns_differ", language))
    n = int(q_prev.shape[0])
    if groups is None:
        groups = ["NA"] * n
    else:
        groups = list(groups)
    if len(groups) != n:
        raise SystemExit(_msg("perm_group_rows", language, rows=n, got=len(groups)))
    if align_groups is None:
        align_groups = []
    else:
        align_groups = list(align_groups)
    if null is None:
        if n_perm > 0:
            raise SystemExit(_msg("perm_null_required", language))
        null_name = "NA"
    elif null not in ("rows", "column"):
        raise SystemExit(_msg("perm_null_choice", language, null=null))
    else:
        null_name = null
    if n_perm > 0:
        seed = _nonneg_int(seed, "perm_seed_negative", language, "seed")
    return {
        "q_prev": q_prev,
        "q_new": q_new,
        "method": method,
        "n_perm": n_perm,
        "seed": seed if n_perm > 0 else 0,
        "null": null_name,
        "mask": mask,
        "groups": groups,
        "align_mode": align_mode,
        "align_groups": align_groups,
        "qmax": qmax,
        "jaccard_set": jaccard_set,
        "jaccard_cut": jaccard_cut,
        "language": language,
    }


def _check_column(column, n_new, language):
    if isinstance(column, bool) or not isinstance(column, (int, np.integer)):
        raise SystemExit(_msg("perm_column_range", language, column=column, last=n_new - 1))
    index = int(column)
    if index < 0 or index >= n_new:
        raise SystemExit(_msg("perm_column_range", language, column=column, last=n_new - 1))
    return index


def _mask_of(ctx, q_new):
    return _alignment_mask(
        ctx["q_prev"], q_new, ctx["groups"], ctx["align_mode"], ctx["align_groups"],
        ctx["qmax"], ctx["mask"], ctx["language"],
    )


def _perm_of(ctx, q_new, mask):
    return _matched_perm(
        ctx["q_prev"], q_new, mask, ctx["method"],
        ctx["jaccard_set"], ctx["jaccard_cut"], ctx["language"],
    )


def _zero_flags(q_prev, q_new, observed):
    """True when the matched new column or its paired old column is all zeros."""
    n_old = int(q_prev.shape[1])
    flags = []
    for index, raw in enumerate(observed):
        new_zero = _all_zero(q_new[:, raw])
        old_zero = _all_zero(q_prev[:, index]) if index < n_old else False
        flags.append(bool(new_zero or old_zero))
    return flags


def _observed(ctx):
    mask = _mask_of(ctx, ctx["q_new"])
    observed = _perm_of(ctx, ctx["q_new"], mask)
    return mask, observed, _zero_flags(ctx["q_prev"], ctx["q_new"], observed)


def _pack(n_perm, n_extreme, null, zero_column):
    if n_extreme == "NA":
        p_value = "NA"
        extreme = "NA"
    else:
        extreme = int(n_extreme)
        # qbar's definition. The leading 1 is the observed statistic.
        p_value = (1.0 + float(extreme)) / float(int(n_perm) + 1)
    return {
        "n_perm": int(n_perm),
        "n_extreme": extreme,
        "p": p_value,
        "null": null,
        "zero_column": bool(zero_column),
    }


def _rows_counts(ctx):
    """One generator, ``n_perm`` row shuffles, counts for every aligned column.

    T is the unrounded score ``match_next`` stores for that old column on
    this replicate's assignment. The leftover score is missing, so that
    count stays ``NA``. ``rng.permutation(n)`` is the only draw in each
    replicate. An empty mask sets T* to 0 and does not call the matcher.
    Any other matcher error stops the run.
    """
    q_new = ctx["q_new"]
    mask = _mask_of(ctx, q_new)
    _observed_perm, scores = _matched_assignment(
        ctx["q_prev"], q_new, mask, ctx["method"],
        ctx["jaccard_set"], ctx["jaccard_cut"], ctx["language"],
    )
    zeros = _zero_flags(ctx["q_prev"], q_new, _observed_perm)
    # None is the leftover slot. T is undefined there, so the formula is not applied.
    counts = ["NA" if score is None else 0 for score in scores]
    rng = np.random.default_rng(ctx["seed"])
    n = int(q_new.shape[0])
    language = ctx["language"]
    for _replicate in range(ctx["n_perm"]):
        # Shuffle rows of the K+1 matrix. q_prev stays in its aligned order.
        order = rng.permutation(n)
        q_star = q_new[order]
        try:
            mask_star = _mask_of(ctx, q_star)
        except SystemExit as exc:
            if not _is_empty_mask(_exit_text(exc), language):
                raise
            # Do not call the matcher. T* is 0, including when T is negative.
            for index, score in enumerate(scores):
                if score is None:
                    continue
                if 0.0 >= score:
                    counts[index] += 1
            continue
        _perm_star, star_scores = _matched_assignment(
            ctx["q_prev"], q_star, mask_star, ctx["method"],
            ctx["jaccard_set"], ctx["jaccard_cut"], ctx["language"],
        )
        for index, score in enumerate(scores):
            if score is None:
                continue
            # The raw index is not the statistic. Use this replicate's score.
            if star_scores[index] >= score:
                counts[index] += 1
    return counts, zeros


def _column_one(ctx, column, mask, observed, zero):
    """Permute the matched new column. Do not re-solve the assignment.

    The observed mask stays fixed. The shuffle is over every row of that
    column, via ``base[rng.permutation(n)]``. Similarity is then taken
    on the observed mask.
    """
    n_old = int(ctx["q_prev"].shape[1])
    if column >= n_old:
        # The leftover slot has no paired old column.
        return _pack(ctx["n_perm"], "NA", "column", zero)
    raw = int(observed[column])
    t_obs = _pair_similarity(
        ctx["q_prev"], ctx["q_new"], column, raw, mask, ctx["method"],
        ctx["jaccard_set"], ctx["jaccard_cut"],
    )
    base = np.asarray(ctx["q_new"][:, raw], dtype=float).reshape(-1).copy()
    q_work = np.array(ctx["q_new"], dtype=float, copy=True)
    rng = np.random.default_rng(ctx["seed"])
    n = int(base.shape[0])
    n_extreme = 0
    for _replicate in range(ctx["n_perm"]):
        # Other columns stay at the values copied into q_work.
        q_work[:, raw] = base[rng.permutation(n)]
        t_star = _pair_similarity(
            ctx["q_prev"], q_work, column, raw, mask, ctx["method"],
            ctx["jaccard_set"], ctx["jaccard_cut"],
        )
        if t_star >= t_obs:
            n_extreme += 1
    return _pack(ctx["n_perm"], n_extreme, "column", zero)


def permutation_p(q_prev, q_new, method, column, n_perm, seed, null, *,
                  mask=None, groups=None, anchor="", align_mode="all", align_groups=None,
                  qmax=0.75, jaccard_set="dominant", jaccard_cut=0.5, language="en"):
    """Return ``n_perm``, ``n_extreme``, ``p``, ``null``, and ``zero_column``.

    ``column`` is the 0-based aligned index. ``anchor`` is accepted and
    not reapplied: pass the previous matrix already in anchor order.
    ``mask``, when set, is combined with the align-mode mask.
    ``n_perm`` of 0 returns ``p`` and ``n_extreme`` as ``NA`` and does
    not draw a seed. ``zero_column`` is still set from the observed match.
    """
    del anchor
    ctx = _prepare(
        q_prev, q_new, method, n_perm, seed, null,
        mask=mask, groups=groups, align_mode=align_mode, align_groups=align_groups,
        qmax=qmax, jaccard_set=jaccard_set, jaccard_cut=jaccard_cut, language=language,
    )
    index = _check_column(column, int(ctx["q_new"].shape[1]), language)
    if ctx["n_perm"] == 0:
        _mask, _observed_perm, zeros = _observed(ctx)
        return _pack(0, "NA", ctx["null"], zeros[index])
    if ctx["null"] == "rows":
        counts, zeros = _rows_counts(ctx)
        return _pack(ctx["n_perm"], counts[index], "rows", zeros[index])
    mask, observed, zeros = _observed(ctx)
    return _column_one(ctx, index, mask, observed, zeros[index])


def permutation_columns(q_prev, q_new, method, n_perm, seed, null, **kwargs):
    """One dict per aligned column, in column order.

    For null ``rows``, every column shares one row-shuffle sequence.
    That sequence is the same one ``permutation_p`` draws for a single
    column with this seed. For null ``column``, each column draws its
    own sequence from the same seed, matching ``permutation_p``.
    """
    ctx = _prepare(
        q_prev, q_new, method, n_perm, seed, null,
        mask=kwargs.get("mask"),
        groups=kwargs.get("groups"),
        align_mode=kwargs.get("align_mode", "all"),
        align_groups=kwargs.get("align_groups"),
        qmax=kwargs.get("qmax", 0.75),
        jaccard_set=kwargs.get("jaccard_set", "dominant"),
        jaccard_cut=kwargs.get("jaccard_cut", 0.5),
        language=kwargs.get("language", "en"),
    )
    n_new = int(ctx["q_new"].shape[1])
    if ctx["n_perm"] == 0:
        _mask, _observed_perm, zeros = _observed(ctx)
        return [_pack(0, "NA", ctx["null"], zeros[index]) for index in range(n_new)]
    if ctx["null"] == "rows":
        counts, zeros = _rows_counts(ctx)
        return [
            _pack(ctx["n_perm"], counts[index], "rows", zeros[index])
            for index in range(n_new)
        ]
    mask, observed, zeros = _observed(ctx)
    return [
        _column_one(ctx, index, mask, observed, zeros[index])
        for index in range(n_new)
    ]
