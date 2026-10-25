"""Order samples inside groups.
"""
from __future__ import annotations

from collections import OrderedDict

import numpy as np

from .io import order_from_file

WITHIN = ("iid", "q", "hclust", "input")


HCLUST_DIST = ("correlation", "euclidean", "braycurtis")


HCLUST_LINK = ("average", "ward", "complete")


HCLUST_PRE = ("none", "dominant")


def check_hclust_opts(dist, link):
    if dist not in HCLUST_DIST:
        raise SystemExit("--hclust-dist 只能是 %s" % "/".join(HCLUST_DIST))
    if link not in HCLUST_LINK:
        raise SystemExit("--hclust-linkage 只能是 %s" % "/".join(HCLUST_LINK))
    if link == "ward" and dist != "euclidean":
        raise SystemExit("--hclust-linkage ward 需要 --hclust-dist euclidean，收到 %s" % dist)


def hclust_order(q, dist="correlation", link="average", olo=False):
    check_hclust_opts(dist, link)
    q = np.asarray(q, dtype=float)
    if q.ndim != 2 or q.shape[0] < 2:
        return list(range(q.shape[0]))
    try:
        from scipy.cluster.hierarchy import leaves_list, linkage, optimal_leaf_ordering
        from scipy.spatial.distance import pdist
    except ImportError as exc:
        raise SystemExit("hclust 需要 scipy（scipy.cluster.hierarchy）") from exc
    work = q.copy()
    if dist == "correlation":
        std = work.std(axis=1)
        for i in np.where(std == 0.0)[0]:
            work[i, 0] += 1e-12
    import warnings
    from scipy.cluster.hierarchy import ClusterWarning
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=ClusterWarning)
        try:
            z = linkage(work, method=link, metric=dist)
            if olo:
                z = optimal_leaf_ordering(z, pdist(work, metric=dist))
        except ValueError as exc:
            if "finite" not in str(exc):
                raise
            raise SystemExit("hclust 距离出现了非有限值（--hclust-dist %s）" % dist) from exc
    return [int(x) for x in leaves_list(z)]


def hclust_block_order(q, dist="correlation", link="average", olo=False, pre="none"):
    """pre=dominant: split rows by their highest column (lowest index on ties), blocks in
    column order C1, C2, ...; hclust inside each block."""
    q = np.asarray(q, dtype=float)
    if pre == "none":
        return hclust_order(q, dist, link, olo)
    if pre != "dominant":
        raise SystemExit("--hclust-pre 只能是 %s" % "/".join(HCLUST_PRE))
    top = q.argmax(axis=1)
    out = []
    for c in range(q.shape[1]):
        ii = [int(i) for i in np.where(top == c)[0]]
        if len(ii) >= 2:
            out.extend(ii[j] for j in hclust_order(q[ii], dist, link, olo))
        else:
            out.extend(ii)
    return out


def sort_block(idxs, mode, iids, q, sort_col, hc=None):
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
        sub = hclust_block_order(q[idxs], **(hc or {}))
        return [idxs[j] for j in sub]
    raise SystemExit("未知的组内排序：%s" % mode)


def build_order(iids, groups, blocks, within, within_group, rest_name, q_sort, q_hclust, sort_col, order_file,
                hc=None):
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
        order.extend(sort_block(idxs, mode, iids, q, col, hc))
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
