"""Write the TSV tables and the alignment report.
"""
from __future__ import annotations

import os

import numpy as np

from .align import col_pearson

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
            f.write("K_to\tn_mask\tpong_sim\tsplit_parent\n" if pong else
                    "K_to\tn_mask\tjaccard\n" if jac else "K_to\tn_mask\tpearson\n")
            for k, info in sorted(meta.items()):
                rs = " ".join("%.3f" % r for r in info["pearson"][:-1])
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


def align_report_rows(aligned, meta, groups, method, perm, low=None):
    cut = REPORT_LOW[method] if low is None else low
    rows = []
    for k_to in sorted(meta):
        info = meta[k_to]
        prev, new, mask = aligned[k_to - 1], aligned[k_to], info["mask"]
        k_old = prev.shape[1]
        for c in range(k_to):
            row = {"K_to": k_to, "column": "C%d" % (c + 1), "raw_column": perm[k_to][c] + 1, "method": method}
            if c < k_old:
                sim = info["pearson"][c]
                shown = "%.3f" % sim
                row.update(matched_from="C%d" % (c + 1), similarity=shown,
                           pearson="%.3f" % col_pearson(prev[mask, c], new[mask, c]),
                           split_parent="", parent_share="", runner_up="", runner_up_share="",
                           low_confidence="yes" if float(shown) < cut else "no")
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
    measure = {"greedy": "Pearson r", "hungarian": "Pearson r", "pong": "pong similarity", "jaccard": "Jaccard"}[method]
    with open(os.path.join(outdir, "align_report.txt"), "w") as f:
        f.write("Alignment report\nmethod: %s (similarity = %s)\nlow confidence: similarity < %g\n" % (method, measure, cut))
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
