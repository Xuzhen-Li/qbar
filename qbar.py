#!/usr/bin/env python3
"""Plot ADMIXTURE Q files: sort people, align columns across K, write a bar.

One command. No R, no CLUMPP. Same-K replicate merging is not done here
(that is CLUMPP: Jakobsson & Rosenberg 2007 Bioinformatics 23:1801,
DOI 10.1093/bioinformatics/btm233).

Cross-K column matching is greedy maximum Pearson correlation, K to K+1.
Label switching itself is described by Alexander, Novembre & Lange 2009
Genome Res 19:1655, DOI 10.1101/gr.094052.109.

Within-group hclust is average linkage on correlation distance (1 − Pearson),
the same criterion as scipy.cluster.hierarchy.linkage(method="average",
metric="correlation"):
https://docs.scipy.org/doc/scipy/reference/generated/scipy.cluster.hierarchy.linkage.html
"""
from __future__ import annotations

import argparse
import csv
import glob
import os
import sys
from collections import OrderedDict

import numpy as np
from PIL import Image, ImageDraw, ImageFont

PALETTE = [
    "#0072b2", "#d55e00", "#009e73", "#cc79a7", "#e69f00",
    "#56b4e9", "#f0e442", "#332288", "#88ccee", "#44aa99",
    "#117733", "#999933", "#ddcc77", "#cc6677", "#882255",
    "#aa4499", "#661100", "#6699cc", "#888888", "#8d6e63",
]
WITHIN = ("iid", "q", "hclust", "input")
FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/Library/Fonts/Arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
]


def norm_hex(text):
    h = text.strip()
    if not h.startswith("#"):
        h = "#" + h
    if len(h) != 7:
        raise SystemExit("颜色要写成 #rrggbb，收到 %s" % text)
    int(h[1:], 16)
    return h.lower()


def hex_rgb(h):
    h = h.lstrip("#")
    return np.array([int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)], dtype=np.uint8)


def hsv_hex(i):
    """Extra colours once PALETTE is used up. Golden-angle hue, s=0.65, v=0.90."""
    hue = (i * 137.508) % 360.0
    s, v = 0.65, 0.90
    c = v * s
    x = c * (1 - abs((hue / 60.0) % 2 - 1))
    m = v - c
    hi = int(hue // 60) % 6
    rgb = [
        (c, x, 0), (x, c, 0), (0, c, x),
        (0, x, c), (x, 0, c), (c, 0, x),
    ][hi]
    vals = [int(round((t + m) * 255)) for t in rgb]
    return "#%02x%02x%02x" % tuple(vals)


def next_free(used, start):
    i = start
    while True:
        if i < len(PALETTE):
            h = PALETTE[i]
        else:
            h = hsv_hex(i)
        if h.lower() not in used:
            return h.lower()
        i += 1


def col_pearson(a, b):
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    a = a - a.mean()
    b = b - b.mean()
    na = float(np.linalg.norm(a))
    nb = float(np.linalg.norm(b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def load_ids(fam, ids_path):
    if fam and ids_path:
        raise SystemExit("--fam 和 --ids 只留一个")
    if not fam and not ids_path:
        raise SystemExit("需要 --fam（PLINK .fam）或 --ids（一行一个 IID，顺序与 Q 的行一致）")
    path = fam or ids_path
    iids = []
    with open(path) as f:
        for line in f:
            parts = line.split()
            if not parts or parts[0].startswith("#"):
                continue
            if fam and len(parts) >= 2:
                iids.append(parts[1])
            else:
                iids.append(parts[0])
    if len(iids) != len(set(iids)):
        raise SystemExit("样本名有重复：%s" % path)
    if not iids:
        raise SystemExit("样本名单是空的：%s" % path)
    return iids


def load_groups(path, iids, id_col, group_col, rest_name):
    groups = [""] * len(iids)
    if not path:
        return [rest_name] * len(iids)
    with open(path, newline="") as f:
        sample = f.read(4096)
        f.seek(0)
        delim = "\t" if sample.count("\t") >= sample.count(",") else ","
        reader = csv.DictReader(f, delimiter=delim)
        if reader.fieldnames is None:
            raise SystemExit("分组表没有表头：%s" % path)
        if id_col not in reader.fieldnames or group_col not in reader.fieldnames:
            raise SystemExit(
                "分组表里没有列 %s / %s。现有列：%s"
                % (id_col, group_col, ", ".join(reader.fieldnames))
            )
        mp = {}
        for row in reader:
            mp[str(row[id_col]).strip()] = (row.get(group_col) or "").strip()
    out = []
    for iid in iids:
        g = mp.get(iid, "").strip()
        out.append(g if g else rest_name)
    return out


def collect_q(items):
    files = []
    for item in items:
        if os.path.isdir(item):
            hits = sorted(glob.glob(os.path.join(item, "*.Q")))
            if not hits:
                raise SystemExit("目录里没有 .Q：%s" % item)
        else:
            hits = sorted(glob.glob(item))
            if not hits:
                if any(ch in item for ch in "*?["):
                    raise SystemExit("没有匹配到 Q：%s" % item)
                hits = [item]
        files.extend(hits)
    uniq = []
    seen = set()
    for f in files:
        if f not in seen:
            seen.add(f)
            uniq.append(f)
    if not uniq:
        raise SystemExit("没有 Q 文件")
    return uniq


def read_q(path):
    if not os.path.isfile(path):
        raise SystemExit("找不到 Q：%s" % path)
    q = np.loadtxt(path, dtype=float)
    if q.ndim == 1:
        q = q.reshape(-1, 1)
    if q.size == 0 or q.ndim != 2:
        raise SystemExit("Q 是空的或不是矩阵：%s" % path)
    return q


def k_of(path, q):
    base = os.path.basename(path)
    # prefix.8.Q -> 8, and it must equal the column count.
    stem, ext = os.path.splitext(base)
    if ext.lower() != ".q":
        raise SystemExit("需要 .Q 文件：%s" % path)
    tail = stem.rsplit(".", 1)[-1] if "." in stem else ""
    k_file = int(tail) if tail.isdigit() else None
    k_col = int(q.shape[1])
    if k_file is not None and k_file != k_col:
        raise SystemExit("%s 文件名是 K=%d，列数是 %d" % (path, k_file, k_col))
    return k_col


def load_q_set(paths):
    q_by_k = {}
    src = {}
    for path in paths:
        q = read_q(path)
        k = k_of(path, q)
        if k in q_by_k:
            raise SystemExit("K=%d 有两个 Q：%s 和 %s" % (k, src[k], path))
        q_by_k[k] = q
        src[k] = path
    return q_by_k, src


def check_shapes(q_by_k, n):
    for k, q in sorted(q_by_k.items()):
        if q.shape[0] != n:
            raise SystemExit("K=%d 的 Q 有 %d 行，样本名单有 %d 行" % (k, q.shape[0], n))
        if np.any(q < -1e-6) or np.any(q > 1.0 + 1e-4):
            raise SystemExit("K=%d 的 Q 有超出 [0,1] 的数" % k)
        bad = np.where(np.abs(q.sum(axis=1) - 1.0) > 0.05)[0]
        if len(bad):
            print("注意：K=%d 有 %d 行人的组分和离 1 超过 0.05，图上多出来的部分留白" % (k, len(bad)), file=sys.stderr)


def hclust_order(q):
    q = np.asarray(q, dtype=float)
    if q.ndim != 2 or q.shape[0] < 2:
        return list(range(q.shape[0]))
    try:
        from scipy.cluster.hierarchy import leaves_list, linkage
    except ImportError as exc:
        raise SystemExit("hclust 需要 scipy（scipy.cluster.hierarchy）") from exc
    work = q.copy()
    std = work.std(axis=1)
    for i in np.where(std == 0.0)[0]:
        work[i, 0] += 1e-12
    import warnings
    from scipy.cluster.hierarchy import ClusterWarning
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=ClusterWarning)
        z = linkage(work, method="average", metric="correlation")
    return [int(x) for x in leaves_list(z)]


def order_from_file(path, iids):
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
        raise SystemExit("顺序文件是空的：%s" % path)
    head = [cell.lower() for cell in lines[0]]
    if "iid" in head and lines[0][head.index("iid")] not in set(iids):
        col = head.index("iid")
        want = [cells[col] for cells in lines[1:] if len(cells) > col]
    else:
        want = [cells[0] for cells in lines]
    if len(want) != len(set(want)):
        raise SystemExit("顺序文件里有重复的样本名：%s" % path)
    pos = {iid: i for i, iid in enumerate(iids)}
    missing = [x for x in want if x not in pos]
    if missing:
        raise SystemExit("顺序文件里有 %d 个名字不在样本名单中，例如 %s" % (len(missing), ", ".join(missing[:5])))
    order = [pos[x] for x in want]
    have = set(want)
    left = [i for i, iid in enumerate(iids) if iid not in have]
    if left:
        print("顺序文件少了 %d 人，这 %d 人按原名单顺序接在最后" % (len(left), len(left)), file=sys.stderr)
    order.extend(left)
    return order


def sort_block(idxs, mode, iids, q, sort_col):
    idxs = list(idxs)
    if mode == "input":
        return idxs
    if mode == "iid":
        return sorted(idxs, key=lambda i: str(iids[i]))
    if mode == "q":
        if q is None:
            raise SystemExit("按组分排序需要对应 K 的 Q")
        mean = q[idxs].mean(axis=0)
        col = int(np.argmax(mean)) if q.shape[1] else 0
        if sort_col is not None:
            col = sort_col
        return sorted(idxs, key=lambda i: (-float(q[i, col]), str(iids[i])))
    if mode == "hclust":
        if q is None or len(idxs) < 2:
            return idxs
        sub = hclust_order(q[idxs])
        return [idxs[j] for j in sub]
    raise SystemExit("未知的组内排序：%s" % mode)


def build_order(iids, groups, blocks, within, within_group, rest_name, q_sort, q_hclust, sort_col, order_file):
    if order_file:
        order = order_from_file(order_file, iids)
        return order, spans_of(order, groups)
    buckets = OrderedDict()
    for i, g in enumerate(groups):
        buckets.setdefault(g, []).append(i)
    if blocks:
        names = list(blocks)
        rest = sorted(k for k in buckets if k not in names)
        names.extend(rest)
    else:
        names = sorted(buckets)
        if rest_name in names:
            names = [n for n in names if n != rest_name] + [rest_name]
    order = []
    for name in names:
        idxs = buckets.get(name, [])
        if not idxs:
            continue
        mode = within_group.get(name, within)
        q = q_hclust if mode == "hclust" else q_sort
        # --sort-col forces one column for every q-sorted block.
        # Without it, each block sorts on its own majority column.
        col = sort_col - 1 if (mode == "q" and sort_col) else None
        order.extend(sort_block(idxs, mode, iids, q, col))
    if len(order) != len(iids) or len(set(order)) != len(iids):
        raise SystemExit("排序结果不是全体样本的一个排列")
    return order, spans_of(order, groups)


def spans_of(order, groups):
    spans = []
    start = 0
    labels = [groups[i] for i in order]
    for j in range(1, len(labels) + 1):
        if j == len(labels) or labels[j] != labels[start]:
            spans.append({"name": labels[start], "start": start, "end": j})
            start = j
    return spans


def anchor_perm(q, groups, anchor):
    k = q.shape[1]
    if not anchor:
        return list(range(k))
    idx = [i for i, g in enumerate(groups) if g == anchor]
    if not idx:
        raise SystemExit("锚定组 %s 在样本里没有人" % anchor)
    qmax = q.max(axis=1)
    j = idx[int(np.argmax(qmax[idx]))]
    c = int(np.argmax(q[j]))
    return [c] + [t for t in range(k) if t != c]


def core_mask(q_prev, q_new, groups, align_groups, qmax_cut):
    """People used to match columns.

    Same rule as c_align.core_match_mask: inside each listed group, keep
    people with qmax above the cut at both K. If a group has none, keep
    that group's single purest person at the lower K.
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
        raise SystemExit("对齐用的人是空的。检查 --align-groups 和 --qmax")
    return m


ALIGN_METHODS = ("greedy", "hungarian", "pong", "jaccard")
JACCARD_SETS = ("dominant", "threshold")


def pearson_matrix(q_prev, q_new, mask):
    """r[c, j] = Pearson between aligned column c of q_prev and raw column j of q_new."""
    k_old = q_prev.shape[1]
    k_new = q_new.shape[1]
    r = np.zeros((k_old, k_new))
    for c in range(k_old):
        for j in range(k_new):
            r[c, j] = col_pearson(q_prev[mask, c], q_new[mask, j])
    return r


def match_next_hungarian(q_prev, q_new, mask):
    """Assignment of old columns to distinct new columns maximising the summed Pearson r.

    Solved with scipy.optimize.linear_sum_assignment(maximize=True).
    The one unassigned new column is put last.
    """
    try:
        from scipy.optimize import linear_sum_assignment
    except ImportError as exc:
        raise SystemExit("--align-method hungarian 需要 scipy（scipy.optimize）") from exc
    k_old = q_prev.shape[1]
    k_new = q_new.shape[1]
    if k_new != k_old + 1:
        raise SystemExit("对齐要求 K 连续，相邻两个 Q 的列数必须差 1")
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


def match_next_pong(q_prev, q_new, mask):
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
        raise SystemExit("--align-method pong 需要 scipy（scipy.optimize）") from exc
    k_old = q_prev.shape[1]
    k_new = q_new.shape[1]
    if k_new != k_old + 1:
        raise SystemExit("对齐要求 K 连续，相邻两个 Q 的列数必须差 1")
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


def match_next_jaccard(q_prev, q_new, mask, kind="dominant", cut=0.5):
    """One-to-one matching maximising summed Jaccard (scipy linear_sum_assignment); leftover goes last."""
    try:
        from scipy.optimize import linear_sum_assignment
    except ImportError as exc:
        raise SystemExit("--align-method jaccard 需要 scipy（scipy.optimize）") from exc
    k_old = q_prev.shape[1]
    k_new = q_new.shape[1]
    if k_new != k_old + 1:
        raise SystemExit("对齐要求 K 连续，相邻两个 Q 的列数必须差 1")
    j = jaccard_matrix(q_prev, q_new, mask, kind, cut)
    rows, cols = linear_sum_assignment(j, maximize=True)
    by_row = dict(zip(rows.tolist(), cols.tolist()))
    perm = [int(by_row[c]) for c in range(k_old)]
    sims = [float(j[c, perm[c]]) for c in range(k_old)]
    perm.append(int([x for x in range(k_new) if x not in set(perm)][0]))
    sims.append(None)
    return perm, sims


def match_next(q_prev, q_new, mask, method="greedy"):
    """q_prev is already aligned. Return raw-column order for q_new."""
    if method == "hungarian":
        return match_next_hungarian(q_prev, q_new, mask)
    k_new = q_new.shape[1]
    k_old = q_prev.shape[1]
    if k_new != k_old + 1:
        raise SystemExit("对齐要求 K 连续，相邻两个 Q 的列数必须差 1")
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
        raise SystemExit("对齐后应该只剩 1 个新列")
    perm.append(int(rest[0]))
    rs.append(None)
    return perm, rs


def align_qs(q_by_k, groups, anchor, mode, align_groups, qmax_cut, do_align, method="greedy",
             jaccard_set="dominant", jaccard_cut=0.5):
    ks = sorted(q_by_k)
    if do_align and len(ks) > 1:
        for a, b in zip(ks, ks[1:]):
            if b != a + 1:
                raise SystemExit("要跨 K 对齐，K 必须连续。缺 K=%d" % (a + 1))
    perm = {}
    aligned = {}
    meta = {}
    if not do_align or len(ks) == 1:
        for k in ks:
            perm[k] = anchor_perm(q_by_k[k], groups, anchor)
            aligned[k] = q_by_k[k][:, perm[k]]
        return aligned, perm, meta
    perm[ks[0]] = anchor_perm(q_by_k[ks[0]], groups, anchor)
    aligned[ks[0]] = q_by_k[ks[0]][:, perm[ks[0]]]
    for k in ks[:-1]:
        if mode == "core":
            if not align_groups:
                raise SystemExit("align-mode core 需要 --align-groups")
            mask = core_mask(aligned[k], q_by_k[k + 1], groups, align_groups, qmax_cut)
        else:
            if align_groups:
                mask = np.array([g in set(align_groups) for g in groups])
            else:
                mask = np.ones(len(groups), dtype=bool)
            if not mask.any():
                raise SystemExit("对齐用的人是空的")
        if method == "pong":
            p, rs, split = match_next_pong(aligned[k], q_by_k[k + 1], mask)
        elif method == "jaccard":
            p, rs = match_next_jaccard(aligned[k], q_by_k[k + 1], mask, jaccard_set, jaccard_cut)
        else:
            p, rs = match_next(aligned[k], q_by_k[k + 1], mask, method)
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
            print("注意：K=%d→%d 有 %d 列的 Pearson < 0.5，这两次的列可能不是同一个解" % (k, k + 1, len(low)), file=sys.stderr)
    return aligned, perm, meta


def column_owners(q, iids, groups, rank):
    k = q.shape[1]
    owners = [[] for _ in range(k)]
    names = sorted(set(groups), key=lambda g: (rank.get(g, 10**6), g))
    qmax = q.max(axis=1)
    for g in names:
        ii = [i for i, x in enumerate(groups) if x == g]
        if not ii:
            continue
        j = ii[int(np.argmax(qmax[ii]))]
        c = int(np.argmax(q[j]))
        owners[c].append((g, iids[j], float(q[j, c])))
    return owners


def parse_colors(items, color_file):
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
                    raise SystemExit("颜色文件每行要是「名字  #rrggbb」：%s" % line)
                raw.append(parts[0] + "=" + parts[1])
    for item in raw:
        if "=" not in item:
            raise SystemExit("颜色写成 组名=#rrggbb 或 C3=#rrggbb，收到 %s" % item)
        key, hx = item.split("=", 1)
        key = key.strip()
        hx = norm_hex(hx)
        if key[:1] in ("C", "c") and key[1:].isdigit():
            col[int(key[1:])] = hx
        else:
            group[key] = hx
    return group, col


def assign_colors(k, owners, group_color, col_color):
    hexes = [None] * k
    used = set()
    for c in range(k):
        if (c + 1) in col_color:
            hx = col_color[c + 1]
            if hx in used:
                hx = next_free(used, c)
            hexes[c] = hx
            used.add(hx)
    for c, ow in enumerate(owners):
        if hexes[c] is not None:
            continue
        for g, _iid, _q in ow:
            if g in group_color and group_color[g] not in used:
                hexes[c] = group_color[g]
                used.add(hexes[c])
                break
    for c in range(k):
        if hexes[c] is None:
            hx = next_free(used, c)
            hexes[c] = hx
            used.add(hx)
    if len(set(hexes)) != k:
        raise SystemExit("内部错误：K=%d 的颜色有重复" % k)
    return hexes


def ancestry_image(q, hexes, height):
    """One pixel column per sample. Column 0 of q is the bottom of the bar."""
    n, k = q.shape
    rgb = np.full((height, n, 3), 255, dtype=np.uint8)
    cols = [hex_rgb(h) for h in hexes]
    for i in range(n):
        bounds = np.cumsum(q[i])
        for y in range(height):
            t = (height - 1 - y) / float(height)
            c = int(np.searchsorted(bounds, t + 1e-12, side="right"))
            if c >= k:
                continue
            rgb[y, i] = cols[c]
    return rgb


def load_font(size):
    for path in FONT_CANDIDATES:
        if os.path.isfile(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def text_wh(font, text):
    box = font.getbbox(text)
    return box[2] - box[0], box[3] - box[1]


def top_mean(q, groups, col):
    best_g, best_mu = "", -1.0
    for g in set(groups):
        idx = [i for i, x in enumerate(groups) if x == g]
        if not idx:
            continue
        mu = float(q[idx, col].mean())
        if mu > best_mu:
            best_g, best_mu = g, mu
    return best_g, best_mu


def column_label(owners_c, q, groups, col):
    if owners_c:
        return "+".join(g for g, _iid, _q in owners_c)
    g, mu = top_mean(q, groups, col)
    return "%s %.2f" % (g, mu)


def legend_lines(q, groups, owners, hexes):
    rows = []
    for c, hx in enumerate(hexes):
        rows.append((hx, "C%d %s" % (c + 1, column_label(owners[c], q, groups, c))))
    return rows


def draw_rotated(base, x, y, text, font, fill):
    w, h = text_wh(font, text)
    tmp = Image.new("RGBA", (w + 4, h + 4), (0, 0, 0, 0))
    ImageDraw.Draw(tmp).text((1, 0), text, font=font, fill=fill)
    rot = tmp.rotate(45, expand=True, resample=Image.Resampling.BICUBIC)
    base.paste(rot, (int(x), int(y)), rot)
    return rot.size


def render(path, rows, spans, bar_w, bar_h, title):
    """rows: list of {k, image(ndarray HxN), legend[(hex, text)]} in K order."""
    font = load_font(15)
    font_s = load_font(13)
    font_k = load_font(16)
    title_font = load_font(18)
    ink = (31, 41, 55, 255)
    left = 56
    gap = 12
    leg_w = 0
    for row in rows:
        for _hx, text in row["legend"]:
            leg_w = max(leg_w, text_wh(font_s, text)[0] + 22)
    leg_w = min(max(leg_w, 80), 420)
    names = [s["name"] for s in spans]
    longest = max([text_wh(font, s)[0] for s in names], default=0)
    rotate = len(spans) > 12 or (spans and bar_w / len(spans) < longest + 8)
    if rotate:
        label_h = int(longest * 0.75) + 28
    else:
        label_h = text_wh(font, "Ag")[1] + 16
    title_h = 32 if title else 8
    n_row = len(rows)
    row_pitch = []
    for row in rows:
        need = 4 + len(row["legend"]) * 18
        row_pitch.append(max(bar_h, need))
    width = left + bar_w + gap + leg_w + 16
    height = title_h + sum(row_pitch) + label_h + 12
    canvas = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(canvas)
    if title:
        draw.text((left, 6), title, font=title_font, fill=(31, 41, 55))
    y = title_h
    n = rows[0]["image"].shape[1]
    for row, pitch in zip(rows, row_pitch):
        img = Image.fromarray(row["image"], mode="RGB")
        img = img.resize((bar_w, bar_h), Image.Resampling.NEAREST)
        bar_y = y + (pitch - bar_h) // 2
        canvas.paste(img, (left, bar_y))
        draw.text((8, bar_y + bar_h // 2 - 8), "K%d" % row["k"], font=font_k, fill=(31, 41, 55))
        lx = left + bar_w + gap
        ly = y + 2
        for hx, text in row["legend"]:
            draw.rectangle([lx, ly + 2, lx + 12, ly + 14], fill=hx)
            draw.text((lx + 16, ly), text, font=font_s, fill=(31, 41, 55))
            ly += 18
        y += pitch
    # group boundaries and names, shared x
    boundary = (148, 163, 184)
    for span in spans:
        if span["start"] <= 0:
            continue
        x = left + int(span["start"] * bar_w / n)
        draw.line([(x, title_h), (x, title_h + sum(row_pitch))], fill=boundary, width=1)
    y_lab = title_h + sum(row_pitch) + 4
    for span in spans:
        px0 = left + int(span["start"] * bar_w / n)
        px1 = left + int(span["end"] * bar_w / n)
        if px1 - px0 < 14:
            continue
        mid = (px0 + px1) // 2
        if rotate:
            draw_rotated(canvas, mid - 6, y_lab, span["name"], font_s, ink)
        else:
            tw, _th = text_wh(font, span["name"])
            draw.text((mid - tw // 2, y_lab), span["name"], font=font, fill=(31, 41, 55))
    folder = os.path.dirname(os.path.abspath(path))
    if folder:
        os.makedirs(folder, exist_ok=True)
    canvas.save(path, dpi=(150, 150))
    if path.lower().endswith(".png"):
        canvas.save(os.path.splitext(path)[0] + ".pdf", "PDF", resolution=150.0)


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


REPORT_LOW = {"greedy": 0.5, "hungarian": 0.5, "pong": 0.8, "jaccard": 0.5}


def parent_shares(q_prev, q_new_col, mask):
    """share[c] = sum_i new_i * prev_ic / sum_i new_i over masked people."""
    w = np.asarray(q_new_col, dtype=float)[mask]
    tot = float(w.sum())
    if tot <= 0.0:
        return np.zeros(q_prev.shape[1])
    return (w[:, None] * np.asarray(q_prev, dtype=float)[mask]).sum(axis=0) / tot


def split_parent_of(q_prev, q_new_col, mask):
    """Old column the new column's membership mostly came from (largest share). Returns (c, share)."""
    shares = parent_shares(q_prev, q_new_col, mask)
    c = int(np.argmax(shares))
    return c, float(shares[c])


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
                row.update(matched_from="C%d" % (c + 1), similarity="%.3f" % sim,
                           pearson="%.3f" % col_pearson(prev[mask, c], new[mask, c]),
                           split_parent="", parent_share="",
                           low_confidence="yes" if sim < cut else "no")
            else:
                if method == "pong":
                    pc = info["split_parent"]
                    share = float(parent_shares(prev, new[:, c], mask)[pc])
                else:
                    pc, share = split_parent_of(prev, new[:, c], mask)
                row.update(matched_from="new", similarity="NA", pearson="NA",
                           split_parent="C%d" % (pc + 1), parent_share="%.3f" % share,
                           low_confidence="NA")
            n_dom, dom = dominant_groups(new, groups, c)
            row["top_groups_mean"] = ";".join("%s:%.3f" % (g, mu) for mu, g in top_groups(new, groups, c))
            row["n_dominant"] = n_dom
            row["top_groups_dominant"] = ";".join("%s:%d" % (g, n) for g, n in dom)
            rows.append(row)
    return rows, cut


REPORT_COLS = ("K_to", "column", "raw_column", "matched_from", "method", "similarity", "pearson", "low_confidence",
               "split_parent", "parent_share", "top_groups_mean", "n_dominant", "top_groups_dominant")


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
                    f.write("  %s new, split from %s (parent share %s); top groups: %s\n"
                            % (r["column"], r["split_parent"], r["parent_share"], r["top_groups_mean"]))
                else:
                    ref = "" if measure == "Pearson r" else ", Pearson r %s" % r["pearson"]
                    f.write("  %s <- %s  %s %s%s%s; top groups: %s\n"
                            % (r["column"], r["matched_from"], measure, r["similarity"], ref,
                               "  LOW CONFIDENCE" if r["low_confidence"] == "yes" else "", r["top_groups_mean"]))
    return rows


def parse_within(items):
    out = {}
    for item in items or []:
        if "=" not in item:
            raise SystemExit("--within-group 写成 组名=iid|q|hclust|input，收到 %s" % item)
        name, mode = item.split("=", 1)
        mode = mode.strip()
        if mode not in WITHIN:
            raise SystemExit("组内排序只能是 %s，收到 %s" % (", ".join(WITHIN), mode))
        out[name.strip()] = mode
    return out


def build_parser():
    p = argparse.ArgumentParser(
        prog="qbar",
        description="读 ADMIXTURE 的 Q，按指定规则排人，跨 K 对齐列，写出结构条形图。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="排序：--order-file 用你给的名单；否则按 --blocks 的组序分块，组内用 --within。\n"
        "组内 iid=名字，q=该组占比最高的那一列从高到低，hclust=平均连锁、距离 1−Pearson，input=Q 里的原顺序。\n"
        "多个 K 默认做 Pearson 贪心对齐，新列放在最上面。--no-align 保持每个 Q 自己的列顺序。",
    )
    p.add_argument("--q", nargs="+", required=True, help="一个或多个 .Q，或带引号的通配符，或一个目录")
    p.add_argument("--fam", help="PLINK .fam，IID 在第 2 列，行序与 Q 相同")
    p.add_argument("--ids", help="一行一个 IID，行序与 Q 相同。与 --fam 二选一")
    p.add_argument("--groups", help="分组表，tsv 或 csv，要有表头")
    p.add_argument("--id-col", default="analysis_IID")
    p.add_argument("--group-col", default="Dong_Grp")
    p.add_argument("--blocks", default="", help="组的从左到右顺序，逗号分隔。没写到的组按名字接在后面")
    p.add_argument("--rest-name", default="NA", help="分组为空的人用这个名字。默认 NA")
    p.add_argument("--within", default="iid", choices=WITHIN, help="每一组内部怎么排。默认 iid")
    p.add_argument("--within-group", action="append", default=[], help="单独改某一组，例如 NA=hclust。可重复")
    p.add_argument("--order-file", help="一行一个 IID，这就是从左到右的顺序。给了它就不再用 --blocks")
    p.add_argument("--sort-k", type=int, help="按组分排序时用哪个 K。默认最大的 K")
    p.add_argument("--sort-col", type=int, help="所有按 q 排序的组都用这一列（从 1 数）。不给就每组用自己占比最高的列")
    p.add_argument("--hclust-k", type=int, help="hclust 用哪个 K。默认与 --sort-k 相同")
    p.add_argument("--align", dest="align", action="store_true")
    p.add_argument("--no-align", dest="align", action="store_false")
    p.set_defaults(align=None)
    p.add_argument("--align-mode", choices=("all", "core"), default="all",
                   help="all=掩码内所有人做 Pearson。core=只留 qmax 超过 --qmax 的人，与 c_align 相同")
    p.add_argument("--align-method", choices=ALIGN_METHODS, default="greedy",
                   help="greedy=按列顺序逐列取 Pearson 最高的未用列（默认）。hungarian=Pearson 总和最大的一一匹配。pong=允许上一 K 的一列拆成两列（Behr 2016），align.tsv 第三列为 pong 相似度并多一列 split_parent。jaccard=按人的集合算 Jaccard 后一一匹配，见 --jaccard-set")
    p.add_argument("--jaccard-set", choices=JACCARD_SETS, default="dominant",
                   help="jaccard 用的集合：dominant=该列是此人最高的列；threshold=此人该列 >= --jaccard-cut。默认 dominant")
    p.add_argument("--jaccard-cut", type=float, default=0.5, help="threshold 集合的阈值。默认 0.5")
    p.add_argument("--align-report", action="store_true",
                   help="另写 align_report.tsv 和 align_report.txt")
    p.add_argument("--align-report-low", type=float,
                   help="低置信阈值。默认 greedy/hungarian/jaccard 0.5，pong 0.8")
    p.add_argument("--align-groups", default="", help="参与对齐的组，逗号分隔。core 模式必填")
    p.add_argument("--qmax", type=float, default=0.75, help="core 模式的 qmax 阈值。默认 0.75")
    p.add_argument("--anchor-group", default="", help="最低 K 把这个组最纯的人的主列放到 C1")
    p.add_argument("--color", action="append", default=[], help="组名=#rrggbb 或 C3=#rrggbb。可重复")
    p.add_argument("--color-file", help="两列：名字 #rrggbb")
    p.add_argument("--title", default="")
    p.add_argument("--width", type=int, default=2200, help="条形图宽度，像素")
    p.add_argument("--bar-height", type=int, default=0, help="每一行条的高度。单个 K 默认 220，多个 K 默认 120")
    p.add_argument("--outdir", required=True)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    files = collect_q(args.q)
    q_by_k, src = load_q_set(files)
    iids = load_ids(args.fam, args.ids)
    check_shapes(q_by_k, len(iids))
    groups = load_groups(args.groups, iids, args.id_col, args.group_col, args.rest_name)
    within_group = parse_within(args.within_group)
    unknown = sorted(set(within_group) - set(groups))
    if unknown:
        print("注意：--within-group 里这些组在样本中没有：%s" % ", ".join(unknown), file=sys.stderr)
    blocks = [x.strip() for x in args.blocks.split(",") if x.strip()] if args.blocks else []
    align_groups = [x.strip() for x in args.align_groups.split(",") if x.strip()]
    do_align = (len(q_by_k) > 1) if args.align is None else args.align
    aligned, perm, meta = align_qs(
        q_by_k, groups, args.anchor_group.strip(), args.align_mode,
        align_groups, args.qmax, do_align, args.align_method,
        args.jaccard_set, args.jaccard_cut,
    )
    ks = sorted(aligned)
    sort_k = args.sort_k or ks[-1]
    hclust_k = args.hclust_k or sort_k
    for name, k in (("--sort-k", sort_k), ("--hclust-k", hclust_k)):
        if k not in aligned:
            raise SystemExit("%s=%d 没有对应的 Q" % (name, k))
    if args.sort_col is not None and (args.sort_col < 1 or args.sort_col > sort_k):
        raise SystemExit("--sort-col 要在 1 到 %d 之间" % sort_k)
    if args.order_file and blocks:
        print("给了 --order-file，--blocks 不用", file=sys.stderr)
    order, spans = build_order(
        iids, groups, blocks, args.within, within_group, args.rest_name,
        aligned[sort_k], aligned[hclust_k], args.sort_col, args.order_file,
    )
    rank = {name: i for i, name in enumerate(blocks)}
    group_color, col_color = parse_colors(args.color, args.color_file)
    owners = {}
    hexes = {}
    for k in ks:
        owners[k] = column_owners(aligned[k], iids, groups, rank)
        hexes[k] = assign_colors(k, owners[k], group_color, col_color)
    bar_h = args.bar_height or (220 if len(ks) == 1 else 120)
    # Draw at native sample width, then scale to --width. Height here is the
    # pre-scale resolution; render() resizes the bar to bar_h.
    rows = []
    for k in ks:
        rows.append({
            "k": k,
            "image": ancestry_image(aligned[k][order], hexes[k], height=max(bar_h, 40)),
            "legend": legend_lines(aligned[k], groups, owners[k], hexes[k]),
        })
    os.makedirs(args.outdir, exist_ok=True)
    if len(rows) == 1:
        out = os.path.join(args.outdir, "bar_K%d.png" % rows[0]["k"])
        render(out, rows, spans, args.width, bar_h, args.title)
        print(out)
    else:
        for row in rows:
            one = os.path.join(args.outdir, "bar_K%d.png" % row["k"])
            render(one, [row], spans, args.width, max(bar_h, 180), args.title)
        panel = os.path.join(args.outdir, "panel.png")
        render(panel, rows, spans, args.width, bar_h, args.title)
        print(panel)
    write_tables(args.outdir, iids, groups, order, spans, perm, owners, hexes, meta, aligned)
    if args.align_report and meta:
        write_align_report(args.outdir, aligned, meta, groups, args.align_method, perm, args.align_report_low)
    with open(os.path.join(args.outdir, "args.txt"), "w") as f:
        f.write(" ".join(sys.argv if argv is None else ["qbar"] + list(argv)) + "\n")
        for k in ks:
            f.write("K%d\t%s\n" % (k, src[k]))
    print("order\t%s" % os.path.join(args.outdir, "order.tsv"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
