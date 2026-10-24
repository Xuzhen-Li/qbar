"""Write the TSV tables and the alignment report.
"""
from __future__ import annotations

import os

import numpy as np

from .align import (
    ALIGN_METHODS, CLUMPP_PERM_LIMIT, GPRIME_METHODS, col_pearson, column_gprime,
    jaccard_matrix, match_next, pong_sim,
)

REPORT_LOW = {"greedy": 0.5, "hungarian": 0.5, "pong": 0.8, "jaccard": 0.5}


REPORT_COLS = ("K_to", "column", "raw_column", "matched_from", "method", "similarity", "pearson", "low_confidence",
               "split_parent", "parent_share", "runner_up", "runner_up_share", "top_groups_mean", "n_dominant", "top_groups_dominant")


def top_mean(q, groups, col):
    best_g, best_mu = "", -1.0
    seen = set()
    for g in groups:
        if g in seen:
            continue
        seen.add(g)
        idx = [i for i, x in enumerate(groups) if x == g]
        mu = float(q[idx, col].mean())
        if mu > best_mu:
            best_g, best_mu = g, mu
    return best_g, best_mu


def column_label(owners_c, q, groups, col):
    if owners_c:
        return "+".join(g for g, _iid, _q in owners_c)
    g, mu = top_mean(q, groups, col)
    return "%s %.2f" % (g, mu)


def write_tables(outdir, iids, groups, order, spans, perm, owners, hexes, meta, aligned):
    os.makedirs(outdir, exist_ok=True)
    with open(os.path.join(outdir, "order.tsv"), "w") as f:
        f.write("rank\tiid\tgroup\n")
        for rank, i in enumerate(order, start=1):
            f.write("%d\t%s\t%s\n" % (rank, iids[i], groups[i]))
    with open(os.path.join(outdir, "blocks.tsv"), "w") as f:
        f.write("group\tstart\tend\tn\n")
        for span in spans:
            f.write("%s\t%d\t%d\t%d\n" % (span["name"], span["start"] + 1, span["end"], span["end"] - span["start"]))
    for k, p in sorted(perm.items()):
        with open(os.path.join(outdir, "perm_K%d.tsv" % k), "w") as f:
            f.write("C\traw\thex\towners\n")
            for c, raw in enumerate(p):
                ow = column_label(owners[k][c], aligned[k], groups, c)
                f.write("C%d\t%d\t%s\t%s\n" % (c + 1, raw + 1, hexes[k][c], ow))
    if meta:
        with open(os.path.join(outdir, "align.tsv"), "w") as f:
            pong = any("split_parent" in info for info in meta.values())
            jac = any("jaccard" in info for info in meta.values())
            gprime = any(info.get("gprime") for info in meta.values())
            if pong:
                header = "K_to\tn_mask\tpong_sim\tsplit_parent\n"
            elif jac:
                header = "K_to\tn_mask\tjaccard\n"
            elif gprime:
                header = "K_to\tn_mask\tgprime\n"
            else:
                header = "K_to\tn_mask\tpearson\n"
            f.write(header)
            for k, info in sorted(meta.items()):
                rs = _align_score_text(info["pearson"])
                if pong:
                    f.write("%d\t%d\t%s\tC%d\n" % (k, info["n_mask"], rs, info["split_parent"] + 1))
                else:
                    f.write("%d\t%d\t%s\n" % (k, info["n_mask"], rs))


def parent_shares(q_prev, q_new_col, mask):
    """share[c] = sum_i new_i * prev_ic / sum_i new_i over masked people."""
    w = np.asarray(q_new_col, dtype=float)[mask]
    tot = float(w.sum())
    if tot <= 0.0:
        return np.zeros(q_prev.shape[1])
    return (w[:, None] * np.asarray(q_prev, dtype=float)[mask]).sum(axis=0) / tot


def split_parent_of(q_prev, q_new_col, mask):
    """Old column the new column's membership mostly came from (largest share, lower column on ties).
    Returns (c, share, runner_c, runner_share); all None when the new column sums to 0."""
    if float(np.asarray(q_new_col, dtype=float)[mask].sum()) <= 0.0:
        return None, None, None, None
    shares = parent_shares(q_prev, q_new_col, mask)
    rank = sorted(range(len(shares)), key=lambda c: (-shares[c], c))
    c = rank[0]
    r = rank[1] if len(rank) > 1 else None
    return c, float(shares[c]), r, (float(shares[r]) if r is not None else None)


def top_groups(q, groups, col, n=3):
    mus = []
    for g in sorted(set(groups)):
        idx = [i for i, x in enumerate(groups) if x == g]
        mus.append((float(q[idx, col].mean()), g))
    mus.sort(key=lambda t: (-t[0], t[1]))
    return mus[:n]


def dominant_groups(q, groups, col, n=3):
    top = q.argmax(axis=1)
    counts = {}
    for i, g in enumerate(groups):
        if top[i] == col:
            counts[g] = counts.get(g, 0) + 1
    out = sorted(counts.items(), key=lambda t: (-t[1], t[0]))
    return int((top == col).sum()), out[:n]


def _report_cut(method, low):
    """Return the low-confidence cut, or None when this method has no default.

    The four original methods keep REPORT_LOW. Methods added later are
    absent from that dict, so the default cut is None unless the caller
    passes one.
    """
    if low is not None:
        return low
    if method in REPORT_LOW:
        return REPORT_LOW[method]
    return None


def _low_confidence(shown, cut):
    if cut is None:
        return "NA"
    return "yes" if float(shown) < cut else "no"


def _pair_score(method, prev, new, mask, partner, dest, jac):
    """Score displayed column ``dest`` against previous column ``partner``."""
    left = prev[mask, partner]
    right = new[mask, dest]
    if method == "pong":
        return pong_sim(left, right)
    if method == "jaccard":
        return float(jac[partner, dest])
    if method in GPRIME_METHODS:
        return column_gprime(left, right)
    return col_pearson(left, right)


def _align_score_text(scores):
    """One token per display column, omitting a trailing unmatched column.

    A trailing None is left off, which is the text written when no swap
    has moved that column. A None in any earlier slot is written ``NA``,
    in the same place as the report row whose ``matched_from`` is ``new``.
    """
    last = len(scores) - 1
    parts = []
    for index, value in enumerate(scores):
        if value is None:
            if index != last:
                parts.append("NA")
        else:
            parts.append("%.3f" % value)
    return " ".join(parts)


def refresh_swapped_scores(aligned, meta, swaps, method, jaccard_set="dominant", jaccard_cut=0.5):
    """Move scores with the displayed columns, then score the pairs again.

    ``swaps[k][i]`` is the pre-swap column now drawn at i. The None that
    marks the unmatched column moves with that column. Every other entry
    is recomputed. When the display index still has a previous column,
    the pair is those two displayed columns. When the matched column has
    moved past the previous K, the pair is the previous column it was
    aligned to. An identity permutation is not a swap. A step whose K
    values were not swapped is left unchanged.
    """
    swapped = {}
    for key, perm in (swaps or {}).items():
        k = int(key)
        order = [int(item) for item in perm]
        if order != list(range(k)):
            swapped[k] = order
    if not swapped or not meta:
        return set(swapped)
    for k_to in sorted(meta):
        k_prev = int(k_to) - 1
        if int(k_to) not in swapped and k_prev not in swapped:
            continue
        info = meta[k_to]
        prev = aligned[k_prev]
        new = aligned[int(k_to)]
        mask = info["mask"]
        if "split_parent" in info and k_prev in swapped:
            info["split_parent"] = swapped[k_prev].index(int(info["split_parent"]))
        old = list(info["pearson"])
        if int(k_to) in swapped:
            perm = swapped[int(k_to)]
            moved = [old[perm[i]] for i in range(len(perm))]
        else:
            perm = list(range(len(old)))
            moved = old
        prev_perm = swapped.get(k_prev)
        n_prev = int(prev.shape[1])
        jac = None
        if method == "jaccard":
            jac = jaccard_matrix(prev, new, mask, jaccard_set, jaccard_cut)
        scores = []
        partners = []
        for index, marker in enumerate(moved):
            if marker is None:
                scores.append(None)
                partners.append(None)
                continue
            source = perm[index]
            if index < n_prev:
                partner = index
            elif source < n_prev:
                if prev_perm is None:
                    partner = source
                else:
                    partner = prev_perm.index(source)
            else:
                scores.append(None)
                partners.append(None)
                continue
            scores.append(_pair_score(method, prev, new, mask, partner, index, jac))
            partners.append(partner)
        info["pearson"] = scores
        info["pair"] = partners
    return set(swapped)


def align_report_rows(aligned, meta, groups, method, perm, low=None):
    cut = _report_cut(method, low)
    rows = []
    for k_to in sorted(meta):
        info = meta[k_to]
        prev, new, mask = aligned[k_to - 1], aligned[k_to], info["mask"]
        for c in range(k_to):
            row = {"K_to": k_to, "column": "C%d" % (c + 1), "raw_column": perm[k_to][c] + 1, "method": method}
            # None marks the unmatched column, wherever a swap has drawn it.
            # pair[c] is the previous column the score was computed against.
            # Without a swap that column is c, the same index as before.
            pair = info.get("pair")
            if info["pearson"][c] is not None:
                partner = c if pair is None else pair[c]
                sim = info["pearson"][c]
                shown = "%.3f" % sim
                row.update(matched_from="C%d" % (partner + 1), similarity=shown,
                           pearson="%.3f" % col_pearson(prev[mask, partner], new[mask, c]),
                           split_parent="", parent_share="", runner_up="", runner_up_share="",
                           low_confidence=_low_confidence(shown, cut))
            else:
                mx, mx_share, ru, ru_share = split_parent_of(prev, new[:, c], mask)
                top_tied = mx is not None and ru_share is not None and mx_share == ru_share
                if method == "pong":
                    pc = info["split_parent"]
                    share = None if mx is None else float(parent_shares(prev, new[:, c], mask)[pc])
                    if mx is not None:
                        ru, ru_share = (mx, mx_share) if mx != pc else (ru, ru_share)
                else:
                    pc, share = mx, mx_share
                    if mx is None:
                        pc = None
                fmt_c = lambda x: "NA" if x is None else "C%d" % (x + 1)
                fmt_s = lambda x: "NA" if x is None else "%.3f" % x
                row.update(matched_from="new", similarity="NA", pearson="NA",
                           split_parent=fmt_c(pc if share is not None else None), parent_share=fmt_s(share),
                           runner_up=fmt_c(ru), runner_up_share=fmt_s(ru_share),
                           low_confidence="NA")
                row["_top_shares_tied"] = top_tied
            n_dom, dom = dominant_groups(new, groups, c)
            row["top_groups_mean"] = ";".join("%s:%.3f" % (g, mu) for mu, g in top_groups(new, groups, c))
            row["n_dominant"] = n_dom
            row["top_groups_dominant"] = ";".join("%s:%d" % (g, n) for g, n in dom)
            rows.append(row)
    return rows, cut


def write_align_report(outdir, aligned, meta, groups, method, perm, low=None):
    rows, cut = align_report_rows(aligned, meta, groups, method, perm, low)
    with open(os.path.join(outdir, "align_report.tsv"), "w") as f:
        f.write("\t".join(REPORT_COLS) + "\n")
        for r in rows:
            f.write("\t".join(str(r[c]) for c in REPORT_COLS) + "\n")
    measure = {
        "greedy": "Pearson r",
        "hungarian": "Pearson r",
        "pong": "pong similarity",
        "jaccard": "Jaccard",
        "clumpp-full": "column G'",
        "clumpp-greedy": "column G'",
        "clumpp-largek": "column G'",
        "clumppling-ilp": "column G'",
    }[method]
    with open(os.path.join(outdir, "align_report.txt"), "w") as f:
        if cut is None:
            low_line = "low confidence: NA"
        else:
            low_line = "low confidence: similarity < %g" % cut
        f.write("Alignment report\nmethod: %s (similarity = %s)\n%s\n" % (method, measure, low_line))
        f.write("split parent: %s\n" % ("pong split pair" if method == "pong" else
                "K-1 column with the largest membership-weighted mean over the new column"))
        for k_to in sorted(meta):
            f.write("\nK=%d -> K=%d (people used: %d)\n" % (k_to - 1, k_to, meta[k_to]["n_mask"]))
            for r in [r for r in rows if r["K_to"] == k_to]:
                if r["matched_from"] == "new":
                    matched_low = any(
                        x["low_confidence"] == "yes"
                        for x in rows
                        if x["K_to"] == k_to and x["matched_from"] != "new"
                    )
                    if r.get("_top_shares_tied"):
                        how = "parent not identified"
                    elif matched_low:
                        how = "not a split"
                    else:
                        how = "split from %s" % r["split_parent"]
                    f.write("  %s new, %s (parent share %s; runner-up %s %s); top groups: %s\n"
                            % (r["column"], how, r["parent_share"], r["runner_up"],
                               r["runner_up_share"], r["top_groups_mean"]))
                else:
                    ref = "" if measure == "Pearson r" else ", Pearson r %s" % r["pearson"]
                    f.write("  %s <- %s  %s %s%s%s; top groups: %s\n"
                            % (r["column"], r["matched_from"], measure, r["similarity"], ref,
                               "  LOW CONFIDENCE" if r["low_confidence"] == "yes" else "", r["top_groups_mean"]))
    return rows


_COMPARE_COLS = (
    "K_to", "column", "method", "matched_from", "similarity", "agrees_with_default",
)

_SCIPY_SYMBOL = {
    "hungarian": "linear_sum_assignment",
    "pong": "linear_sum_assignment",
    "jaccard": "linear_sum_assignment",
    "clumppling-ilp": "milp",
}


def _score_text(value):
    if value is None:
        return "NA"
    return "%.3f" % float(value)


def _scipy_import_ok(method):
    """True when this method does not need scipy, or the symbol imports."""
    symbol = _SCIPY_SYMBOL.get(method)
    if symbol is None:
        return True
    try:
        from scipy import optimize
    except ImportError:
        return False
    return hasattr(optimize, symbol)


def _compare_skip_reason(method, k_to):
    """Why this method is left out of one K step, or None when it can run."""
    if method in ("clumpp-full", "clumpp-greedy") and k_to > CLUMPP_PERM_LIMIT:
        return "K+1 is above 8"
    if not _scipy_import_ok(method):
        return "scipy import failed"
    return None


def write_align_compare(outdir, q_by_k, aligned, meta, perm, chosen,
                        jaccard_set="dominant", jaccard_cut=0.5):
    """Write align_compare.tsv and align_compare.txt for one finished run.

    Each method sees the chosen method's already aligned previous matrix
    and the raw next Q, with that step's mask. The chosen alignment is
    not changed. The text names who shares that mapping and who does not.
    It does not declare a better method.
    """
    os.makedirs(outdir, exist_ok=True)
    rows = []
    sections = []
    for k_to in sorted(meta):
        k_from = k_to - 1
        mask = meta[k_to]["mask"]
        chosen_perm = list(perm[k_to])
        same = []
        different = []
        skipped = []
        for method in ALIGN_METHODS:
            reason = _compare_skip_reason(method, k_to)
            if reason is not None:
                skipped.append((method, reason))
                continue
            result = match_next(
                aligned[k_from], q_by_k[k_to], mask, method,
                jaccard_set, jaccard_cut,
            )
            method_perm = list(result[0])
            scores = list(result[1])
            shown = [_score_text(scores[c]) for c in range(k_to)]
            agrees_all = method_perm == chosen_perm
            entry = "%s (%s)" % (method, ", ".join(shown))
            if agrees_all:
                same.append(entry)
            else:
                different.append(entry)
            for c in range(k_to):
                agrees = "yes" if method_perm[c] == chosen_perm[c] else "no"
                rows.append([
                    str(k_to),
                    "C%d" % (c + 1),
                    method,
                    str(method_perm[c] + 1),
                    shown[c],
                    agrees,
                ])
        sections.append((k_from, k_to, same, different, skipped))
    with open(os.path.join(outdir, "align_compare.tsv"), "w") as handle:
        handle.write("\t".join(_COMPARE_COLS) + "\n")
        for row in rows:
            handle.write("\t".join(row) + "\n")
    with open(os.path.join(outdir, "align_compare.txt"), "w") as handle:
        handle.write("No method is declared better.\n")
        handle.write("Chosen method: %s\n" % chosen)
        for k_from, k_to, same, different, skipped in sections:
            handle.write("\nK=%d -> K=%d\n" % (k_from, k_to))
            handle.write("Same mapping as %s: %s\n" % (
                chosen, "; ".join(same) if same else "none",
            ))
            handle.write("Different mapping from %s: %s\n" % (
                chosen, "; ".join(different) if different else "none",
            ))
            for method, reason in skipped:
                handle.write("%s was not compared: %s.\n" % (method, reason))
    return rows
