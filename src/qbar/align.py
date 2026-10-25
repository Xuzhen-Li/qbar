"""Match columns from one K to the next.
"""
from __future__ import annotations

import itertools
import sys

import numpy as np

from .messages import text as _msg

# qbar stops clumpp-full and clumpp-greedy when K+1 is above this.
# The number is qbar's own. CLUMPAK uses MAX_K 8 to switch to a greedy
# search. CLUMPP does not define a hard stop at 8.
CLUMPP_PERM_LIMIT = 8

ALIGN_METHODS = (
    "greedy", "hungarian", "pong", "jaccard",
    "clumpp-full", "clumpp-greedy", "clumpp-largek", "clumppling-ilp",
)

# Methods whose align.tsv score is column G', not Pearson, pong, or Jaccard.
GPRIME_METHODS = (
    "clumpp-full", "clumpp-greedy", "clumpp-largek", "clumppling-ilp",
)

# Same-K replicate pairs use Pearson for these methods.
REPLICATE_PEARSON_METHODS = ("greedy", "hungarian") + GPRIME_METHODS


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


def _pong_one(a, b):
    """``pong_sim`` for two contiguous 1d float64 vectors of equal length.

    When every entry has ``a + b > 0``, boolean indexing copies that whole
    sequence. The full subtraction is the same sequence, so ``np.dot``
    matches the previous body. A shorter mask still subtracts the kept
    entries in index order and dots that vector.
    """
    keep = (a + b) > 0
    n = int(keep.sum())
    if n == 0:
        return 0.0
    if n == a.shape[0]:
        d = a - b
    else:
        d = a[keep] - b[keep]
    return float(1.0 - np.sqrt(np.dot(d, d) / (2.0 * n)))


def _pong_vector(column):
    """1d float64 vector. This is the conversion ``pong_sim`` applies."""
    column = np.asarray(column, dtype=float)
    return np.ascontiguousarray(column)


def _pong_columns(matrix):
    """Contiguous float64 columns. A column that is already contiguous is kept."""
    matrix = np.asarray(matrix, dtype=float)
    cols = []
    for index in range(int(matrix.shape[1])):
        col = matrix[:, index]
        if col.dtype == np.float64 and col.ndim == 1 and col.flags.c_contiguous:
            cols.append(col)
        else:
            cols.append(np.ascontiguousarray(col, dtype=np.float64))
    return cols


def _pong_score_cols(left_cols, right_cols):
    """``out[c, j]`` equals ``_pong_one(left_cols[c], right_cols[j])``."""
    out = np.empty((len(left_cols), len(right_cols)), dtype=float)
    for c, left in enumerate(left_cols):
        for j, right in enumerate(right_cols):
            out[c, j] = _pong_one(left, right)
    return out


def _pong_merge_block(n_rows, n_pairs, merge_buf):
    """F-order float64 block for ``n_pairs`` columns of length ``n_rows``.

    ``merge_buf`` is used when it already has room. Otherwise this allocates
    a block for this call. The block is not stored on the module.
    """
    rows = int(n_rows)
    pairs = int(n_pairs)
    if (
        isinstance(merge_buf, np.ndarray)
        and merge_buf.dtype == np.float64
        and merge_buf.ndim == 2
        and merge_buf.flags.f_contiguous
        and int(merge_buf.shape[0]) >= rows
        and int(merge_buf.shape[1]) >= pairs
    ):
        return merge_buf
    return np.empty((rows, pairs), dtype=np.float64, order="F")


def _pong_sim_matrix(left, right):
    """``out[c, j]`` equals ``pong_sim(left[:, c], right[:, j])``."""
    return _pong_score_cols(_pong_columns(left), _pong_columns(right))


def pong_sim(a, b):
    """pong default similarity (Behr et al. 2016, manual eq. 1):
    1 - sqrt(sum((a-b)^2 over N*) / (2|N*|)), N* = people with a+b > 0."""
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    if a.ndim == 1 and b.ndim == 1 and a.shape[0] == b.shape[0]:
        return _pong_one(np.ascontiguousarray(a), np.ascontiguousarray(b))
    keep = (a + b) > 0
    n = int(keep.sum())
    if n == 0:
        return 0.0
    d = a[keep] - b[keep]
    return float(1.0 - np.sqrt(np.dot(d, d) / (2.0 * n)))


def match_next_pong(q_prev, q_new, mask, *, language="en", merge_buf=None):
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
    # Each raw pair is scored once. Each merged column a+b is scored once.
    # Both values are the pong_sim floats, so the assignment uses the same
    # matrix the pair loop used to rebuild on every visit.
    # The sum is taken in the input dtype. ``pong_sim`` upcasts that sum.
    # The upcast columns are written into one F-order block. ``align_qs``
    # passes a block sized for the largest step. A column of that block is
    # already contiguous, so scoring does not allocate a second copy.
    # Column views are dropped before this function returns.
    old_cols = _pong_columns(old)
    new_cols = _pong_columns(new)
    base = _pong_score_cols(old_cols, new_cols)
    pairs = [(a, b) for a in range(k_new) for b in range(a + 1, k_new)]
    if pairs:
        buf = _pong_merge_block(int(old.shape[0]), len(pairs), merge_buf)
        block = buf[: int(old.shape[0]), : len(pairs)]
        for index, (a, b) in enumerate(pairs):
            added = new[:, a] + new[:, b]
            block[:, index] = _pong_vector(added)
        merged_cols = [block[:, index] for index in range(len(pairs))]
        del new_cols, added
        merged_sim = _pong_score_cols(old_cols, merged_cols)
        del old_cols, merged_cols
        pair_at = {pair: index for index, pair in enumerate(pairs)}
    else:
        merged_sim = None
        pair_at = {}
        del old_cols, new_cols
    best = None
    for a, b in pairs:
        cols = [j for j in range(k_new) if j not in (a, b)] + [(a, b)]
        sim = np.empty((k_old, len(cols)), dtype=float)
        for m_i, j in enumerate(cols):
            if isinstance(j, tuple):
                sim[:, m_i] = merged_sim[:, pair_at[j]]
            else:
                sim[:, m_i] = base[:, j]
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
            sa, sb = float(base[c, a]), float(base[c, b])
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


def _require_one_new_column(q_prev, q_new, language):
    if q_new.shape[1] != q_prev.shape[1] + 1:
        raise SystemExit(_msg("k_columns_differ", language))


def _masked_pair(q_prev, q_new, mask):
    """Rows kept by the alignment mask. C in the G' formulas is this row count."""
    q = np.asarray(q_prev, dtype=float)[mask]
    p = np.asarray(q_new, dtype=float)[mask]
    return q, p


def _pad_zero_column(q):
    """Q-hat: Q with one zero column on the right."""
    pad = np.zeros((q.shape[0], 1), dtype=float)
    return np.concatenate([np.asarray(q, dtype=float), pad], axis=1)


def _gprime(sum_sq, n_rows):
    """G' = 1 - ||diff|| / sqrt(2C), with ||diff|| the Frobenius or L2 norm."""
    return float(1.0 - np.sqrt(sum_sq) / np.sqrt(2.0 * float(n_rows)))


def column_gprime(a, b):
    """Column G' of two length-C vectors: 1 - ||a - b||_2 / sqrt(2C)."""
    diff = np.asarray(a, dtype=float) - np.asarray(b, dtype=float)
    return _gprime(float(np.dot(diff, diff)), diff.shape[0])


def matrix_gprime(left, right):
    """Matrix G' = 1 - ||left - right||_F / sqrt(2C)."""
    diff = np.asarray(left, dtype=float) - np.asarray(right, dtype=float)
    return _gprime(float(np.sum(diff * diff)), diff.shape[0])


def _old_column_gprime(reference, p, perm):
    """Column G' for each old column. The leftover P column is None.

    reference[:, c] for c < K is the column the score is taken against.
    For the clumpp methods that column is Q-hat[:, c]. For clumppling-ilp
    it is the unpadded Q column. Those two agree for c < K.
    """
    k_old = len(perm) - 1
    scores = [column_gprime(reference[:, c], p[:, perm[c]]) for c in range(k_old)]
    scores.append(None)
    return scores


def _best_gprime_perm(qhat, p):
    """Lexicographically smallest permutation of P that maximises matrix G'.

    itertools.permutations(range(k)) is lexicographic order. A later
    permutation replaces the current one only when its G' is strictly larger.
    """
    k1 = p.shape[1]
    best_g = None
    best_perm = None
    for perm in itertools.permutations(range(k1)):
        ordered = p[:, list(perm)]
        g = matrix_gprime(qhat, ordered)
        if best_g is None or g > best_g:
            best_g = g
            best_perm = perm
    return list(best_perm)


def _refuse_clumpp_perm_search(k1, method, language):
    if k1 > CLUMPP_PERM_LIMIT:
        raise SystemExit(_msg("clumpp_perm_limit", language, method=method, k1=k1))


def _match_clumpp_full_search(q_prev, q_new, mask, method, language):
    """Pad Q and maximise matrix G' over permutations of P."""
    _require_one_new_column(q_prev, q_new, language)
    k1 = int(q_new.shape[1])
    _refuse_clumpp_perm_search(k1, method, language)
    q, p = _masked_pair(q_prev, q_new, mask)
    qhat = _pad_zero_column(q)
    perm = _best_gprime_perm(qhat, p)
    # The P column on the padded zero column is last in perm.
    return perm, _old_column_gprime(qhat, p, perm)


def match_next_clumpp_full(q_prev, q_new, mask, *, language="en"):
    """qbar adaptation of CLUMPP FullSearch for one K to one K+1.

    Q is padded with one zero column. The permutation of P maximises
    G' = 1 - ||Q-hat - P[:, perm]||_F / sqrt(2C). Ties keep the
    lexicographically smallest perm. K+1 above 8 is refused.
    """
    return _match_clumpp_full_search(q_prev, q_new, mask, "clumpp-full", language)


def match_next_clumpp_greedy(q_prev, q_new, mask, seed=None, repeats=None, *, language="en"):
    """Same permutation as clumpp-full on one K to one K+1 pair.

    seed and repeats are accepted and ignored. No command-line flags are
    added for them. Published CLUMPP Greedy differs only when more than
    two runs share one K.
    """
    del seed, repeats
    return _match_clumpp_full_search(q_prev, q_new, mask, "clumpp-greedy", language)


def match_next_clumpp_largek(q_prev, q_new, mask, *, language="en"):
    """Lock column pairs by column G' after the same zero padding.

    Repeatedly lock the highest remaining pair that reuses no column,
    until K+1 pairs are locked. Ties: smaller new-column index b, then
    smaller old-column index a. The P column locked to the pad is last.
    There is no stop at K+1 = 8. This is not a claim that matrix G' is
    maximised.
    """
    _require_one_new_column(q_prev, q_new, language)
    q, p = _masked_pair(q_prev, q_new, mask)
    qhat = _pad_zero_column(q)
    k1 = int(p.shape[1])
    score = np.empty((k1, k1), dtype=float)
    for a in range(k1):
        for b in range(k1):
            score[a, b] = column_gprime(qhat[:, a], p[:, b])
    remaining_a = set(range(k1))
    remaining_b = set(range(k1))
    locked = {}
    while remaining_a:
        best_key = None
        best_pair = None
        for a in remaining_a:
            for b in remaining_b:
                # Highest column G', then smaller b, then smaller a.
                key = (float(score[a, b]), -b, -a)
                if best_key is None or key > best_key:
                    best_key = key
                    best_pair = (a, b)
        a, b = best_pair
        locked[a] = b
        remaining_a.remove(a)
        remaining_b.remove(b)
    perm = [locked[a] for a in range(k1)]
    return perm, _old_column_gprime(qhat, p, perm)


def clumppling_cost_matrix(q, p):
    """Paper cost C_ij on already masked matrices.

    q is C by K, p is C by K+1. i indexes columns of P and j indexes
    columns of Q. C_ij = (1/(2C)) * sum over rows (P_li - Q_lj)^2.
    """
    q = np.asarray(q, dtype=float)
    p = np.asarray(p, dtype=float)
    n_rows = int(q.shape[0])
    k_old = int(q.shape[1])
    k_new = int(p.shape[1])
    cost = np.empty((k_new, k_old), dtype=float)
    scale = 1.0 / (2.0 * float(n_rows))
    for i in range(k_new):
        for j in range(k_old):
            diff = p[:, i] - q[:, j]
            cost[i, j] = scale * float(np.dot(diff, diff))
    return cost


def clumppling_perm_from_w(cost, w, *, language="en"):
    """Turn a binary assignment into the qbar perm.

    cost and w have shape (K+1, K). Each row of w sums to 1. Exactly one
    column of w sums to 2. That column keeps the child with the smaller
    cost, and the smaller row index on a tie. The other child is last.
    Every other column keeps its single child at that position.
    A status-0 solution that is not that assignment stops with a message.
    """
    cost = np.asarray(cost, dtype=float)
    rounded = np.rint(np.asarray(w, dtype=float))
    k_new, k_old = cost.shape
    perm = [None] * (k_old + 1)
    n_doubled = 0
    for j in range(k_old):
        assigned = [i for i in range(k_new) if rounded[i, j] == 1.0]
        if len(assigned) == 1:
            perm[j] = assigned[0]
            continue
        if len(assigned) != 2:
            raise SystemExit(_msg(
                "clumppling_assignment_column",
                language,
                column=j,
                n=len(assigned),
            ))
        n_doubled += 1
        keep, extra = sorted(assigned, key=lambda i: (float(cost[i, j]), i))
        perm[j] = keep
        perm[k_old] = extra
    if n_doubled != 1 or any(item is None for item in perm):
        raise SystemExit(_msg("clumppling_assignment_double", language))
    return [int(item) for item in perm]


def _milp_clumppling(cost, language):
    """Minimise sum W_ij C_ij. Return (W, objective)."""
    try:
        from scipy.optimize import Bounds, LinearConstraint, milp
    except ImportError as exc:
        raise SystemExit(_msg("clumppling_needs_scipy", language)) from exc
    k_new, k_old = cost.shape
    nvar = k_new * k_old
    # Row-major: variable i * K + j is W_ij.
    objective = np.ascontiguousarray(cost, dtype=float).ravel()
    row_coef = np.zeros((k_new, nvar), dtype=float)
    for i in range(k_new):
        row_coef[i, i * k_old:(i + 1) * k_old] = 1.0
    col_coef = np.zeros((k_old, nvar), dtype=float)
    for j in range(k_old):
        for i in range(k_new):
            col_coef[j, i * k_old + j] = 1.0
    constraints = (
        LinearConstraint(row_coef, np.ones(k_new), np.ones(k_new)),
        LinearConstraint(col_coef, np.ones(k_old), np.full(k_old, np.inf)),
    )
    result = milp(
        objective,
        integrality=np.ones(nvar, dtype=int),
        bounds=Bounds(0.0, 1.0),
        constraints=constraints,
    )
    status = int(result.status)
    if status != 0:
        message = "" if result.message is None else str(result.message)
        raise SystemExit(_msg(
            "clumppling_not_optimal", language, status=status, message=message,
        ))
    w = np.asarray(result.x, dtype=float).reshape(k_new, k_old)
    return w, float(result.fun)


def clumppling_ilp_objective(q_prev, q_new, mask, *, language="en"):
    """Optimal paper cost of clumppling-ilp on this pair."""
    _require_one_new_column(q_prev, q_new, language)
    q, p = _masked_pair(q_prev, q_new, mask)
    _w, fun = _milp_clumppling(clumppling_cost_matrix(q, p), language)
    return fun


def match_next_clumppling_ilp(q_prev, q_new, mask, *, language="en"):
    """Assign K+1 columns of P onto K columns of Q by the paper ILP.

    Minimise sum W_ij C_ij with scipy.optimize.milp. Each new column is
    used once. Each old column is used at least once. The doubled old
    column keeps the child with the smaller cost. The other child is last.
    Scores are column G' on the unpadded Q columns.
    """
    _require_one_new_column(q_prev, q_new, language)
    q, p = _masked_pair(q_prev, q_new, mask)
    cost = clumppling_cost_matrix(q, p)
    w, _fun = _milp_clumppling(cost, language)
    perm = clumppling_perm_from_w(cost, w, language=language)
    return perm, _old_column_gprime(q, p, perm)


def match_next(q_prev, q_new, mask, method="greedy", jaccard_set="dominant", jaccard_cut=0.5, *, language="en"):
    """q_prev is already aligned. Return raw-column order for q_new.

    Named methods call those matchers. "pong" includes the split dict.
    Any other method, including the default "greedy", is greedy Pearson.
    """
    if method == "hungarian":
        return match_next_hungarian(q_prev, q_new, mask, language=language)
    if method == "pong":
        return match_next_pong(q_prev, q_new, mask, language=language)
    if method == "jaccard":
        return match_next_jaccard(q_prev, q_new, mask, jaccard_set, jaccard_cut, language=language)
    if method == "clumpp-full":
        return match_next_clumpp_full(q_prev, q_new, mask, language=language)
    if method == "clumpp-greedy":
        return match_next_clumpp_greedy(q_prev, q_new, mask, language=language)
    if method == "clumpp-largek":
        return match_next_clumpp_largek(q_prev, q_new, mask, language=language)
    if method == "clumppling-ilp":
        return match_next_clumppling_ilp(q_prev, q_new, mask, language=language)
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
             jaccard_set="dominant", jaccard_cut=0.5, *, language="en", warn=True, row_mask=None):
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
    # One merged-column block for this call, sized for the largest step.
    # It is passed down and dropped when this alignment returns. Another
    # call, including one on another thread, gets its own block.
    merge_buf = None
    if method == "pong":
        n_rows = int(q_by_k[ks[0]].shape[0])
        max_k = int(ks[-1])
        n_pairs = max_k * (max_k - 1) // 2
        if n_pairs > 0:
            merge_buf = np.empty((n_rows, n_pairs), dtype=np.float64, order="F")
    try:
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
            if row_mask is not None:
                extra = np.asarray(row_mask, dtype=bool)
                if extra.ndim != 1 or extra.shape[0] != mask.shape[0]:
                    got = int(extra.shape[0]) if extra.ndim >= 1 else int(extra.size)
                    raise SystemExit(_msg(
                        "bootstrap_mask_shape", language, rows=int(mask.shape[0]), got=got,
                    ))
                mask = mask & extra
                if not mask.any():
                    raise SystemExit(_msg("align_empty", language))
            if method == "pong":
                p, rs, split = match_next_pong(
                    aligned[k], q_by_k[k + 1], mask, language=language, merge_buf=merge_buf,
                )
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
            if method in GPRIME_METHODS:
                meta[k + 1]["gprime"] = True
                continue
            # Pearson < 0.5 on stderr is only for greedy and hungarian.
            low = [r for r in rs[:-1] if r is not None and r < 0.5]
            if warn and low:
                print(
                    _msg("pearson_low", language, k_from=k, k_to=k + 1, n=len(low)),
                    file=sys.stderr,
                )
        return aligned, perm, meta
    finally:
        merge_buf = None
