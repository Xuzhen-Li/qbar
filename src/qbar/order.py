"""Order samples inside groups.
"""
from __future__ import annotations

from collections import OrderedDict

import numpy as np

from .io import order_from_file
from .messages import text as _msg

WITHIN = ("iid", "q", "hclust", "input")


HCLUST_DIST = ("correlation", "euclidean", "braycurtis")


HCLUST_LINK = ("average", "ward", "complete")


HCLUST_PRE = ("none", "dominant")


ORDER_MODES = ("within", "global-hclust", "group-hclust")


GROUP_ORDERS = ("input", "hclust")


DENDROGRAMS = ("none", "top")


# 4 GiB. Used when --hclust-max-bytes is omitted, and only for the all-rows
# vector and the between-group vector. 0 on the command line means no cap.
DEFAULT_HCLUST_MAX_BYTES = 4294967296


LINKAGE_COLUMNS = ("row", "idx1", "idx2", "distance", "count")


def pdist_nbytes(n):
    """Bytes in one condensed float64 distance vector, N*(N-1)/2*8.

    N below 2 has no pairs. The result is a Python int. Nothing is allocated.
    """
    n = int(n)
    if n < 2:
        return 0
    return n * (n - 1) // 2 * 8


def check_hclust_bytes(n, cap, *, language="en"):
    """Refuse before a distance vector is built when its bytes exceed ``cap``.

    ``None`` and ``0`` mean no cap. A negative cap is an error. Equality with
    the cap is allowed: the run stops only when the byte count is greater.
    """
    if cap is None:
        return
    if isinstance(cap, bool) or not isinstance(cap, int):
        raise SystemExit(_msg("hclust_max_bytes_type", language, cap=cap))
    if cap < 0:
        raise SystemExit(_msg("hclust_max_bytes_negative", language, cap=cap))
    if cap == 0:
        return
    n = int(n)
    nbytes = pdist_nbytes(n)
    if nbytes > cap:
        raise SystemExit(_msg(
            "hclust_over_cap", language, n=n, nbytes=nbytes, cap=cap,
        ))


def resolve_hclust_max_bytes(explicit, order_mode, tree, *, language="en"):
    """Return the byte cap for one tree, or None when that tree has no cap.

    ``explicit`` is None when ``--hclust-max-bytes`` is omitted. ``0`` means
    no cap. A negative value is an error. A positive value applies to every
    tree the caller asks about. When the flag is omitted, ``global-hclust``
    caps the all-rows vector and ``group-hclust`` caps the between-group
    vector, both at 4294967296. Within-group trees stay uncapped. ``within``
    has no cap.
    """
    if tree not in ("global", "between", "within"):
        raise SystemExit(_msg("hclust_tree_kind", language, tree=tree))
    if order_mode not in ORDER_MODES:
        raise SystemExit(_msg(
            "order_mode_choice", language, mode=order_mode, choices="/".join(ORDER_MODES),
        ))
    if explicit is not None:
        if isinstance(explicit, bool) or not isinstance(explicit, int):
            raise SystemExit(_msg("hclust_max_bytes_type", language, cap=explicit))
        if explicit < 0:
            raise SystemExit(_msg("hclust_max_bytes_negative", language, cap=explicit))
        if explicit == 0:
            return None
        return explicit
    if order_mode == "global-hclust" and tree == "global":
        return DEFAULT_HCLUST_MAX_BYTES
    if order_mode == "group-hclust" and tree == "between":
        return DEFAULT_HCLUST_MAX_BYTES
    return None


def cap_for_tree(explicit, order_mode, tree, tree_n, full_n, *, language="en"):
    """Cap for a tree that is about to be built.

    An omitted cap on ``global-hclust`` applies only to a tree that uses every
    row. A dominant block that is a proper subset stays uncapped unless the
    user set a byte value. That is what the refusal text points at when it
    names ``--hclust-pre dominant``.
    """
    cap = resolve_hclust_max_bytes(explicit, order_mode, tree, language=language)
    if (
        explicit is None
        and order_mode == "global-hclust"
        and tree == "global"
        and int(tree_n) != int(full_n)
    ):
        return None
    return cap


def check_hclust_opts(dist, link, *, language="en"):
    if dist not in HCLUST_DIST:
        raise SystemExit(_msg("hclust_dist", language, choices="/".join(HCLUST_DIST)))
    if link not in HCLUST_LINK:
        raise SystemExit(_msg("hclust_linkage", language, choices="/".join(HCLUST_LINK)))
    if link == "ward" and dist != "euclidean":
        raise SystemExit(_msg("ward_needs_euclidean", language, dist=dist))


def _leaves(z):
    from scipy.cluster.hierarchy import leaves_list
    return [int(x) for x in leaves_list(z)]


def linkage_matrix(q, dist="correlation", link="average", olo=False, *, language="en", max_bytes=None):
    """SciPy linkage for ``q``, shape ``(n - 1, 4)``.

    The same rules as ``hclust_order``: Ward needs euclidean, a constant row
    under correlation gets ``1e-12`` added to column 0, a non-finite distance
    is an error, and fewer than 2 rows returns shape ``(0, 4)``. ``olo``
    replaces the matrix with ``optimal_leaf_ordering``. ``max_bytes`` is
    checked before SciPy builds the distance vector. ``None`` and ``0`` mean
    no cap.
    """
    check_hclust_opts(dist, link, language=language)
    q = np.asarray(q, dtype=float)
    if q.ndim != 2 or q.shape[0] < 2:
        return np.zeros((0, 4), dtype=float)
    check_hclust_bytes(q.shape[0], max_bytes, language=language)
    try:
        from scipy.cluster.hierarchy import linkage, optimal_leaf_ordering
        from scipy.spatial.distance import pdist
    except ImportError as exc:
        raise SystemExit(_msg("hclust_needs_scipy", language)) from exc
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
            raise SystemExit(_msg("hclust_nonfinite", language, dist=dist)) from exc
    return np.asarray(z, dtype=float)


def hclust_order(q, dist="correlation", link="average", olo=False, *, language="en", max_bytes=None):
    z = linkage_matrix(q, dist, link, olo, language=language, max_bytes=max_bytes)
    q = np.asarray(q, dtype=float)
    if z.shape[0] == 0:
        return list(range(q.shape[0]))
    return _leaves(z)


def _covers_all(subset, n):
    return len(subset) == n and list(subset) == list(range(n))


def hclust_block_trees(
    q, dist="correlation", link="average", olo=False, pre="none", *,
    language="en", explicit_cap=None, order_mode="within", tree_kind="within",
):
    """Return ``(order, trees)``.

    ``trees`` is a list of ``(subset, Z)``. ``subset`` holds the row indices
    in ``q`` that were clustered, in the order passed to SciPy. ``pre=none``
    is one tree. ``pre=dominant`` is one tree per highest-column block that
    has at least two rows. The byte cap is resolved per tree.
    """
    q = np.asarray(q, dtype=float)
    if pre == "none":
        full_n = q.shape[0] if q.ndim == 2 else 0
        cap = cap_for_tree(
            explicit_cap, order_mode, tree_kind, full_n, full_n, language=language,
        )
        z = linkage_matrix(q, dist, link, olo, language=language, max_bytes=cap)
        order = list(range(q.shape[0])) if z.shape[0] == 0 else _leaves(z)
        trees = []
        if z.shape[0] > 0:
            trees.append((list(range(q.shape[0])), z))
        return order, trees
    if pre != "dominant":
        raise SystemExit(_msg("hclust_pre", language, choices="/".join(HCLUST_PRE)))
    full_n = q.shape[0]
    top = q.argmax(axis=1)
    out = []
    trees = []
    for c in range(q.shape[1]):
        ii = [int(i) for i in np.where(top == c)[0]]
        if len(ii) >= 2:
            cap = cap_for_tree(
                explicit_cap, order_mode, tree_kind, len(ii), full_n, language=language,
            )
            z = linkage_matrix(q[ii], dist, link, olo, language=language, max_bytes=cap)
            local = list(range(len(ii))) if z.shape[0] == 0 else _leaves(z)
            out.extend(ii[j] for j in local)
            if z.shape[0] > 0:
                trees.append((ii, z))
        else:
            out.extend(ii)
    return out, trees


def hclust_block_order(q, dist="correlation", link="average", olo=False, pre="none", *, language="en", max_bytes=None):
    """pre=dominant: split rows by their highest column (lowest index on ties), blocks in
    column order C1, C2, ...; hclust inside each block.

    ``max_bytes`` None means no cap, including inside each dominant block.
    A positive value caps every block.
    """
    # None and 0 both mean no cap. A positive value is an explicit cap, so the
    # within-mode resolver applies it to every block.
    explicit = 0 if max_bytes is None else max_bytes
    order, _trees = hclust_block_trees(
        q, dist, link, olo, pre,
        language=language, explicit_cap=explicit, order_mode="within", tree_kind="within",
    )
    return order


def sort_block(idxs, mode, iids, q, sort_col, hc=None, *, language="en", max_bytes=None):
    idxs = list(idxs)
    if mode == "input":
        return idxs
    if mode == "iid":
        return sorted(idxs, key=lambda i: str(iids[i]))
    if mode == "q":
        if q is None:
            raise SystemExit(_msg("sort_needs_q", language))
        mean = q[idxs].mean(axis=0)
        col = int(np.argmax(mean)) if q.shape[1] else 0
        if sort_col is not None:
            col = sort_col
        return sorted(idxs, key=lambda i: (-float(q[i, col]), str(iids[i])))
    if mode == "hclust":
        if q is None or len(idxs) < 2:
            return idxs
        sub = hclust_block_order(q[idxs], language=language, max_bytes=max_bytes, **(hc or {}))
        return [idxs[j] for j in sub]
    raise SystemExit(_msg("unknown_within", language, mode=mode))


def build_order(iids, groups, blocks, within, within_group, rest_name, q_sort, q_hclust, sort_col, order_file,
                hc=None, *, language="en", max_bytes=None):
    if order_file:
        order = order_from_file(order_file, iids, language=language)
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
        order.extend(sort_block(idxs, mode, iids, q, col, hc, language=language, max_bytes=max_bytes))
    if len(order) != len(iids) or len(set(order)) != len(iids):
        raise SystemExit(_msg("order_not_permutation", language))
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


def group_input_names(groups):
    """Group labels in the order they first appear."""
    names = []
    seen = set()
    for name in groups:
        if name in seen:
            continue
        seen.add(name)
        names.append(name)
    return names


def _group_buckets(groups):
    names = group_input_names(groups)
    buckets = OrderedDict((name, []) for name in names)
    for i, name in enumerate(groups):
        buckets[name].append(i)
    return buckets


def _hc_parts(hc):
    hc = hc or {}
    return (
        hc.get("dist", "correlation"),
        hc.get("link", "average"),
        hc.get("olo", False),
        hc.get("pre", "none"),
    )


def _cluster_group_means(q, groups, dist, link, olo, *, language="en", max_bytes=None):
    """Return input names, leaf-ordered names, buckets, and the between-group linkage.

    One group, or a group list shorter than 2, keeps that input order and an
    empty linkage. The mean Q row of each group is qbar's own distance input.
    """
    q = np.asarray(q, dtype=float)
    groups = list(groups)
    if q.ndim != 2 or len(groups) != q.shape[0]:
        rows = q.shape[0] if q.ndim == 2 else 0
        raise SystemExit(_msg(
            "group_hclust_shape", language, groups=len(groups), rows=rows,
        ))
    buckets = _group_buckets(groups)
    names = list(buckets)
    if len(names) < 2:
        return names, list(names), buckets, np.zeros((0, 4), dtype=float)
    means = np.vstack([q[buckets[name]].mean(axis=0) for name in names])
    z = linkage_matrix(means, dist, link, olo, language=language, max_bytes=max_bytes)
    local = list(range(len(names))) if z.shape[0] == 0 else _leaves(z)
    ordered = [names[i] for i in local]
    return names, ordered, buckets, z


def group_hclust_order(q, groups, dist="correlation", link="average", olo=False, *, language="en", max_bytes=None):
    """Return row indices with each group kept contiguous.

    Groups follow SciPy's leaf order on the mean Q row. A single group keeps
    the rows in input order. Rows inside a group stay in input order. The
    caller applies ``--within`` on top of that.
    """
    _names, ordered, buckets, _z = _cluster_group_means(
        q, groups, dist, link, olo, language=language, max_bytes=max_bytes,
    )
    order = []
    for name in ordered:
        order.extend(buckets[name])
    return order


def _permutation_ok(order, n, *, language):
    if len(order) != n or len(set(order)) != n:
        raise SystemExit(_msg("order_not_permutation", language))


def _sample_layers(order, trees):
    rank_of = {sample: rank for rank, sample in enumerate(order)}
    layers = []
    for subset, z in trees:
        layers.append({
            "kind": "samples",
            "Z": z,
            "ranks": [rank_of[sample] for sample in subset],
        })
    return layers


def _one_tree_matrix(trees, n, pre):
    """The linkage file for one all-rows tree, or None when the order is a forest.

    ``pre=none`` always has a matrix (header only when N < 2). ``dominant``
    writes a matrix only when one block contains every row. Several blocks
    are not one SciPy linkage, and they do not build the all-rows vector.
    """
    if len(trees) == 1 and _covers_all(trees[0][0], n):
        return trees[0][1]
    if pre == "none":
        return np.zeros((0, 4), dtype=float)
    return None


def validate_order_flags(order_mode, group_order, dendrogram, explicit_cap, order_file, *, language="en"):
    """Reject flag combinations before any output file is created."""
    if order_mode not in ORDER_MODES:
        raise SystemExit(_msg(
            "order_mode_choice", language, mode=order_mode, choices="/".join(ORDER_MODES),
        ))
    if group_order not in GROUP_ORDERS:
        raise SystemExit(_msg(
            "group_order_choice", language, mode=group_order, choices="/".join(GROUP_ORDERS),
        ))
    if dendrogram not in DENDROGRAMS:
        raise SystemExit(_msg(
            "dendrogram_choice", language, mode=dendrogram, choices="/".join(DENDROGRAMS),
        ))
    resolve_hclust_max_bytes(explicit_cap, order_mode, "within", language=language)
    if group_order == "hclust" and order_mode != "group-hclust":
        raise SystemExit(_msg("group_order_needs_mode", language))
    if dendrogram == "top":
        allowed = order_mode == "global-hclust" or (
            order_mode == "group-hclust" and group_order == "hclust"
        )
        if not allowed:
            raise SystemExit(_msg("dendrogram_needs_tree", language))
    if order_file and order_mode != "within":
        raise SystemExit(_msg("order_file_with_mode", language, mode=order_mode))


def apply_order_mode(
    iids, groups, blocks, within, within_group, rest_name,
    q_sort, q_hclust, sort_col, order_file, hc,
    order_mode="within", group_order="input", explicit_cap=None, *, language="en",
):
    """Return order, spans, linkage matrices, an index name list, and dendrogram layers.

    ``--order-mode within`` calls ``build_order`` and writes no linkage.
    Linkage matrices are ``(filename, Z)`` in write order. ``index_groups``
    is the input-order name list when a between-groups or group-indexed file
    is written, and None otherwise. Dendrogram layers are returned for the
    new modes even when the caller will not draw them.
    """
    dist, link, olo, pre = _hc_parts(hc)
    if order_mode == "within":
        cap = resolve_hclust_max_bytes(explicit_cap, "within", "within", language=language)
        order, spans = build_order(
            iids, groups, blocks, within, within_group, rest_name,
            q_sort, q_hclust, sort_col, order_file, hc,
            language=language, max_bytes=cap,
        )
        return {
            "order": order,
            "spans": spans,
            "matrices": [],
            "index_groups": None,
            "layers": [],
        }
    if order_mode == "global-hclust":
        q = np.asarray(q_hclust, dtype=float)
        order, trees = hclust_block_trees(
            q, dist, link, olo, pre,
            language=language, explicit_cap=explicit_cap,
            order_mode="global-hclust", tree_kind="global",
        )
        _permutation_ok(order, len(iids), language=language)
        spans = spans_of(order, groups)
        matrices = []
        z = _one_tree_matrix(trees, q.shape[0] if q.ndim == 2 else 0, pre)
        if z is not None:
            matrices.append(("linkage_global.tsv", z))
        return {
            "order": order,
            "spans": spans,
            "matrices": matrices,
            "index_groups": None,
            "layers": _sample_layers(order, trees),
        }
    if order_mode != "group-hclust":
        raise SystemExit(_msg(
            "order_mode_choice", language, mode=order_mode, choices="/".join(ORDER_MODES),
        ))
    cap_between = resolve_hclust_max_bytes(
        explicit_cap, "group-hclust", "between", language=language,
    )
    if group_order == "hclust":
        names, ordered_names, buckets, z_between = _cluster_group_means(
            q_hclust, groups, dist, link, olo, language=language, max_bytes=cap_between,
        )
    else:
        buckets = _group_buckets(groups)
        names = list(buckets)
        ordered_names = list(names)
        z_between = None
    order = []
    group_files = []
    name_to_n = {name: i + 1 for i, name in enumerate(names)}
    for name in ordered_names:
        idxs = list(buckets[name])
        mode = within_group.get(name, within)
        q = q_hclust if mode == "hclust" else q_sort
        col = sort_col - 1 if (mode == "q" and sort_col) else None
        if mode == "hclust" and q is not None and len(idxs) >= 2:
            local, trees = hclust_block_trees(
                np.asarray(q, dtype=float)[idxs], dist, link, olo, pre,
                language=language, explicit_cap=explicit_cap,
                order_mode="group-hclust", tree_kind="within",
            )
            order.extend(idxs[j] for j in local)
            if len(trees) == 1 and _covers_all(trees[0][0], len(idxs)):
                group_files.append((name_to_n[name], trees[0][1]))
        else:
            order.extend(sort_block(idxs, mode, iids, q, col, hc, language=language))
    _permutation_ok(order, len(iids), language=language)
    spans = spans_of(order, groups)
    matrices = []
    layers = []
    if z_between is not None:
        matrices.append(("linkage_between_groups.tsv", z_between))
        if z_between.shape[0] > 0:
            span_of = {}
            for span in spans:
                span_of.setdefault(span["name"], span)
            layers.append({
                "kind": "groups",
                "Z": z_between,
                "spans": [span_of[name] for name in names],
            })
    group_files.sort(key=lambda item: item[0])
    for n, z in group_files:
        matrices.append(("linkage_group_%d.tsv" % n, z))
    index_groups = names if matrices else None
    return {
        "order": order,
        "spans": spans,
        "matrices": matrices,
        "index_groups": index_groups,
        "layers": layers,
    }


def format_linkage_distance(value):
    """Six digits after the decimal, the same ``%.6f`` as the other TSV floats."""
    return "%.6f" % float(value)


def write_linkage_tsv(path, z):
    """Write one SciPy linkage. ``row`` is the 0-based merge index.

    ``idx1`` and ``idx2`` use SciPy's coding: ``0 .. n-2`` would be too small
    a description, because original observations are ``0 .. n-1`` and later
    rows refer to merged clusters at ``n + row``. ``distance`` uses
    ``%.6f``. ``count`` is the integer number of observations.
    """
    z = np.asarray(z, dtype=float).reshape(-1, 4)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("\t".join(LINKAGE_COLUMNS) + "\n")
        for i in range(z.shape[0]):
            handle.write("%d\t%d\t%d\t%s\t%d\n" % (
                i,
                int(round(float(z[i, 0]))),
                int(round(float(z[i, 1]))),
                format_linkage_distance(z[i, 2]),
                int(round(float(z[i, 3]))),
            ))


def write_linkage_index(path, names):
    """Write ``index`` and ``group`` for the input order of groups.

    ``index`` is 1-based. It is the ``n`` in ``linkage_group_<n>.tsv``. It is
    also one more than the 0-based SciPy leaf index in
    ``linkage_between_groups.tsv``: leaf ``j`` is the group with index ``j + 1``.
    Group names are not used in file names.
    """
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("index\tgroup\n")
        for n, name in enumerate(names, start=1):
            handle.write("%d\t%s\n" % (n, name))
