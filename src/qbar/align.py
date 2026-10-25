"""Match columns from one K to the next.
"""
from __future__ import annotations

import sys

import numpy as np

from .messages import text as _msg

ALIGN_METHODS = ("greedy", "hungarian", "pong", "jaccard")


JACCARD_SETS = ("dominant", "threshold")


def col_pearson(a, b):
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    if np.ptp(a) == 0.0 or np.ptp(b) == 0.0:
        return 0.0
    a = a - a.mean()
    b = b - b.mean()
    na = float(np.linalg.norm(a))
    nb = float(np.linalg.norm(b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def anchor_perm(q, groups, anchor, *, language="en"):
    k = q.shape[1]
    if not anchor:
        return list(range(k))
    idx = [i for i, g in enumerate(groups) if g == anchor]
    if not idx:
        raise SystemExit(_msg("anchor_missing", language, anchor=anchor))
    qmax = q.max(axis=1)
    j = idx[int(np.argmax(qmax[idx]))]
    c = int(np.argmax(q[j]))
    return [c] + [t for t in range(k) if t != c]


def core_mask(q_prev, q_new, groups, align_groups, qmax_cut, *, language="en"):
    """People used to match columns.

    Inside each listed group, keep people with qmax > cut at both K.
    If a group has none, keep that group's single purest person at the
    lower K.
    """
    n = q_prev.shape[0]
    m = np.zeros(n, dtype=bool)
    qmax_p = np.asarray(q_prev, dtype=float).max(axis=1)
    qmax_n = np.asarray(q_new, dtype=float).max(axis=1)
    for g in align_groups:
        in_g = np.array([x == g for x in groups])
        both = in_g & (qmax_p > qmax_cut) & (qmax_n > qmax_cut)
        if both.any():
            m |= both
        elif in_g.any():
            ii = np.where(in_g)[0]
            j = int(ii[int(np.argmax(qmax_p[ii]))])
            m[j] = True
    if not m.any():
        raise SystemExit(_msg("align_empty_check", language))
    return m


def pearson_matrix(q_prev, q_new, mask):
    """r[c, j] = Pearson between aligned column c of q_prev and raw column j of q_new."""
    k_old = q_prev.shape[1]
    k_new = q_new.shape[1]
    r = np.zeros((k_old, k_new))
    for c in range(k_old):
        for j in range(k_new):
            r[c, j] = col_pearson(q_prev[mask, c], q_new[mask, j])
    return r


def match_next_hungarian(q_prev, q_new, mask, *, language="en"):
    """Assignment of old columns to distinct new columns maximising the summed Pearson r.

    Solved with scipy.optimize.linear_sum_assignment(maximize=True).
    The one unassigned new column is put last.
    """
    try:
        from scipy.optimize import linear_sum_assignment
    except ImportError as exc:
        raise SystemExit(_msg("align_needs_scipy", language, method="hungarian")) from exc
    k_old = q_prev.shape[1]
    k_new = q_new.shape[1]
    if k_new != k_old + 1:
        raise SystemExit(_msg("k_columns_differ", language))
    r = pearson_matrix(q_prev, q_new, mask)
    rows, cols = linear_sum_assignment(r, maximize=True)
    by_row = dict(zip(rows.tolist(), cols.tolist()))
    perm = [int(by_row[c]) for c in range(k_old)]
    rs = [float(r[c, perm[c]]) for c in range(k_old)]
    rest = [j for j in range(k_new) if j not in set(perm)]
    perm.append(int(rest[0]))
    rs.append(None)
    return perm, rs


def pong_sim(a, b):
    """pong default similarity (Behr et al. 2016, manual eq. 1):
    1 - sqrt(sum((a-b)^2 over N*) / (2|N*|)), N* = people with a+b > 0."""
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    keep = (a + b) > 0
    n = int(keep.sum())
    if n == 0:
        return 0.0
    d = a[keep] - b[keep]
    return float(1.0 - np.sqrt(np.dot(d, d) / (2.0 * n)))


def match_next_pong(q_prev, q_new, mask, *, language="en"):
    """Split-aware matching between adjacent K, after pong (Behr et al. 2016).

    For each pair (a, b) of new columns, sum them into one column, match the k old
    columns to the k merged columns by maximum summed similarity, and keep the pair
    with the highest mean similarity. The old column matched to a+b is the split
    parent: of a and b, the one more similar to it takes its place, the other goes last.
    Returns (perm, sims, split) with split = {"parent": c, "pair": (raw_a, raw_b)}.
    """
    try:
        from scipy.optimize import linear_sum_assignment
    except ImportError as exc:
        raise SystemExit(_msg("align_needs_scipy", language, method="pong")) from exc
    k_old = q_prev.shape[1]
    k_new = q_new.shape[1]
    if k_new != k_old + 1:
        raise SystemExit(_msg("k_columns_differ", language))
    old = q_prev[mask]
    new = q_new[mask]
    best = None
    for a in range(k_new):
        for b in range(a + 1, k_new):
            cols = [j for j in range(k_new) if j not in (a, b)] + [(a, b)]
            merged = [new[:, j] if not isinstance(j, tuple) else new[:, a] + new[:, b] for j in cols]
            sim = np.array([[pong_sim(old[:, c], m) for m in merged] for c in range(k_old)])
            rows, cidx = linear_sum_assignment(sim, maximize=True)
            score = float(sim[rows, cidx].mean())
            if best is None or score > best[0]:
                best = (score, cols, dict(zip(rows.tolist(), cidx.tolist())), sim)
    _score, cols, by_row, sim = best
    perm, sims, split = [], [], None
    for c in range(k_old):
        j = cols[by_row[c]]
        if isinstance(j, tuple):
            a, b = j
            sa, sb = pong_sim(old[:, c], new[:, a]), pong_sim(old[:, c], new[:, b])
            keep, rest = (a, b) if sa >= sb else (b, a)
            perm.append(int(keep))
            split = {"parent": c, "pair": (int(keep), int(rest))}
        else:
            perm.append(int(j))
        sims.append(float(sim[c, by_row[c]]))
    perm.append(int(split["pair"][1]))
    sims.append(None)
    return perm, sims, split


def member_sets(q, mask, kind, cut):
    """Per column, the boolean set of masked people: dominant = column is the row's
    argmax (lowest index on ties); threshold = q >= cut."""
    q = np.asarray(q, dtype=float)[mask]
    if kind == "dominant":
        top = q.argmax(axis=1)
        return np.stack([top == c for c in range(q.shape[1])], axis=1)
    return q >= cut


def jaccard_matrix(q_prev, q_new, mask, kind="dominant", cut=0.5):
    """j[c, k] = |A_c & B_k| / |A_c | B_k| on member_sets; 0 when both are empty."""
    a = member_sets(q_prev, mask, kind, cut)
    b = member_sets(q_new, mask, kind, cut)
    j = np.zeros((a.shape[1], b.shape[1]))
    for c in range(a.shape[1]):
        for k in range(b.shape[1]):
            union = int((a[:, c] | b[:, k]).sum())
            if union:
                j[c, k] = int((a[:, c] & b[:, k]).sum()) / union
    return j


def match_next_jaccard(q_prev, q_new, mask, kind="dominant", cut=0.5, *, language="en"):
    """One-to-one matching maximising summed Jaccard (scipy linear_sum_assignment); leftover goes last."""
    try:
        from scipy.optimize import linear_sum_assignment
    except ImportError as exc:
        raise SystemExit(_msg("align_needs_scipy", language, method="jaccard")) from exc
    k_old = q_prev.shape[1]
    k_new = q_new.shape[1]
    if k_new != k_old + 1:
        raise SystemExit(_msg("k_columns_differ", language))
    j = jaccard_matrix(q_prev, q_new, mask, kind, cut)
    rows, cols = linear_sum_assignment(j, maximize=True)
    by_row = dict(zip(rows.tolist(), cols.tolist()))
    perm = [int(by_row[c]) for c in range(k_old)]
    sims = [float(j[c, perm[c]]) for c in range(k_old)]
    perm.append(int([x for x in range(k_new) if x not in set(perm)][0]))
    sims.append(None)
    return perm, sims


def match_next(q_prev, q_new, mask, method="greedy", jaccard_set="dominant", jaccard_cut=0.5, *, language="en"):
    """q_prev is already aligned. Return raw-column order for q_new.

    "hungarian", "pong", and "jaccard" call those matchers and return the
    same value. "pong" includes the split dict. Any other method, including
    the default "greedy", is greedy Pearson.
    """
    if method == "hungarian":
        return match_next_hungarian(q_prev, q_new, mask, language=language)
    if method == "pong":
        return match_next_pong(q_prev, q_new, mask, language=language)
    if method == "jaccard":
        return match_next_jaccard(q_prev, q_new, mask, jaccard_set, jaccard_cut, language=language)
    k_new = q_new.shape[1]
    k_old = q_prev.shape[1]
    if k_new != k_old + 1:
        raise SystemExit(_msg("k_columns_differ", language))
    used = set()
    perm = []
    rs = []
    for c in range(k_old):
        best_j, best_r = None, -2.0
        for j in range(k_new):
            if j in used:
                continue
            r = col_pearson(q_prev[mask, c], q_new[mask, j])
            if r > best_r:
                best_r, best_j = r, j
        perm.append(int(best_j))
        used.add(best_j)
        rs.append(float(best_r))
    rest = [j for j in range(k_new) if j not in used]
    if len(rest) != 1:
        raise SystemExit(_msg("align_one_new_column", language))
    perm.append(int(rest[0]))
    rs.append(None)
    return perm, rs


def align_qs(q_by_k, groups, anchor, mode, align_groups, qmax_cut, do_align, method="greedy",
             jaccard_set="dominant", jaccard_cut=0.5, *, language="en"):
    ks = sorted(q_by_k)
    if do_align and len(ks) > 1:
        for a, b in zip(ks, ks[1:]):
            if b != a + 1:
                raise SystemExit(_msg("k_gap", language, k=a + 1))
    perm = {}
    aligned = {}
    meta = {}
    if not do_align or len(ks) == 1:
        for k in ks:
            perm[k] = anchor_perm(q_by_k[k], groups, anchor, language=language)
            aligned[k] = q_by_k[k][:, perm[k]]
        return aligned, perm, meta
    perm[ks[0]] = anchor_perm(q_by_k[ks[0]], groups, anchor, language=language)
    aligned[ks[0]] = q_by_k[ks[0]][:, perm[ks[0]]]
    for k in ks[:-1]:
        if mode == "core":
            if not align_groups:
                raise SystemExit(_msg("core_needs_groups", language))
            mask = core_mask(aligned[k], q_by_k[k + 1], groups, align_groups, qmax_cut, language=language)
        else:
            if align_groups:
                mask = np.array([g in set(align_groups) for g in groups])
            else:
                mask = np.ones(len(groups), dtype=bool)
            if not mask.any():
                raise SystemExit(_msg("align_empty", language))
        if method == "pong":
            p, rs, split = match_next_pong(aligned[k], q_by_k[k + 1], mask, language=language)
        elif method == "jaccard":
            p, rs = match_next_jaccard(
                aligned[k], q_by_k[k + 1], mask, jaccard_set, jaccard_cut, language=language,
            )
        else:
            p, rs = match_next(aligned[k], q_by_k[k + 1], mask, method, language=language)
        perm[k + 1] = p
        aligned[k + 1] = q_by_k[k + 1][:, p]
        meta[k + 1] = {"n_mask": int(mask.sum()), "pearson": rs, "mask": mask}
        if method == "pong":
            meta[k + 1]["split_parent"] = split["parent"]
            continue
        if method == "jaccard":
            meta[k + 1]["jaccard"] = True
            continue
        low = [r for r in rs[:-1] if r is not None and r < 0.5]
        if low:
            print(
                _msg("pearson_low", language, k_from=k, k_to=k + 1, n=len(low)),
                file=sys.stderr,
            )
    return aligned, perm, meta
