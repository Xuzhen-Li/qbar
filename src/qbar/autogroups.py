"""Groups derived from an aligned Q matrix, or from PCA scores.

``major`` and ``threshold`` read Q only. ``hclust`` and ``kmeans`` can
cluster either that Q or the leading columns of a PLINK 1.9 eigenvec.
The names are qbar's own. They are not a published classifier.

The summary file carries one fixed sentence: groups derived from Q are
for display and ordering, and using them as evidence for the same Q is
circular. Agreement with a known groups file is a count table. This
module does not compute an adjusted Rand index.
"""
from __future__ import annotations

import os

import numpy as np

from .messages import text as _msg
from .order import cap_for_tree, linkage_matrix

AUTO_METHODS = ("none", "major", "threshold", "hclust", "kmeans")
CLUSTER_METHODS = ("hclust", "kmeans")
KMEANS_RESTARTS = 10
CIRCULAR_SENTENCE = (
    "Groups derived from Q are for display and ordering. "
    "Using them as evidence for the same Q is circular."
)
GROUPS_AUTO_COLUMNS = ("id", "group", "method", "parameters", "max_q", "top_column")


def auto_hclust_cap(explicit, n, *, language="en"):
    """Byte cap for an all-rows auto-group tree.

    This is the F1 resolution for a tree that uses every row: an omitted
    flag is 4294967296, ``0`` is no cap, and a positive integer is that cap.
    """
    return cap_for_tree(
        explicit, "global-hclust", "global", n, n, language=language,
    )


def _show_cut(cut):
    try:
        value = float(cut)
    except (TypeError, ValueError):
        return str(cut)
    if not np.isfinite(value):
        return str(cut)
    return _compact(value)


def _compact(value):
    text = "%.6f" % float(value)
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    if text in ("", "-", "-0"):
        return "0"
    return text


def check_admix_cut(cut, *, language="en"):
    """Accept a cut in (0, 1]. 0 and values above 1 are errors. 1 is allowed."""
    try:
        value = float(cut)
    except (TypeError, ValueError):
        raise SystemExit(_msg("admix_cut_bounds", language, cut=cut)) from None
    if isinstance(cut, bool) or not np.isfinite(value) or not (value > 0.0 and value <= 1.0):
        raise SystemExit(_msg("admix_cut_bounds", language, cut=_show_cut(cut)))
    return value


def _check_auto_g(auto_g, *, language="en"):
    if isinstance(auto_g, bool) or not isinstance(auto_g, (int, np.integer)) or int(auto_g) < 1:
        raise SystemExit(_msg("auto_g_range", language, g=auto_g))
    return int(auto_g)


def validate_auto_flags(
    method, auto_k, admix_cut, auto_g, auto_seed, pca, pca_n, *, language="en",
):
    """Reject flag combinations that do not need the Q matrix.

    A stored default is allowed while ``--auto-groups`` is ``none``.
    Any other auto flag is an error, the same rule as ``--flow-weight``
    while ``--cluster-flow`` is ``none``.
    """
    if method not in AUTO_METHODS:
        raise SystemExit(_msg("auto_groups_choice", language, method=method))
    if pca_n is not None and not pca:
        raise SystemExit(_msg("pca_n_needs_pca", language))
    if pca and pca_n is None:
        raise SystemExit(_msg("pca_needs_n", language))
    if pca and method not in CLUSTER_METHODS:
        raise SystemExit(_msg("pca_needs_cluster", language))
    if auto_k is not None and method == "none":
        raise SystemExit(_msg("auto_k_needs_groups", language, k=auto_k))
    if auto_g is not None and method not in CLUSTER_METHODS:
        raise SystemExit(_msg("auto_g_needs_cluster", language, g=auto_g))
    if method in CLUSTER_METHODS:
        if auto_g is None:
            raise SystemExit(_msg("auto_g_required", language, method=method))
        _check_auto_g(auto_g, language=language)
    if pca_n is not None:
        if isinstance(pca_n, bool) or not isinstance(pca_n, (int, np.integer)) or int(pca_n) < 1:
            raise SystemExit(_msg("pca_n_low", language, n=pca_n))
    if isinstance(auto_seed, bool) or not isinstance(auto_seed, (int, np.integer)):
        raise SystemExit(_msg("auto_seed_needs_kmeans", language, seed=auto_seed))
    if method != "kmeans" and int(auto_seed) != 0:
        raise SystemExit(_msg("auto_seed_needs_kmeans", language, seed=auto_seed))
    try:
        cut_value = float(admix_cut)
    except (TypeError, ValueError):
        cut_value = None
    if method == "threshold":
        check_admix_cut(admix_cut, language=language)
    elif cut_value != 0.5:
        raise SystemExit(_msg(
            "admix_cut_needs_threshold", language, cut=_show_cut(admix_cut),
        ))


def check_auto_g_against_n(auto_g, n, *, language="en"):
    g = _check_auto_g(auto_g, language=language)
    if g > int(n):
        raise SystemExit(_msg("auto_g_above_n", language, g=g, n=int(n)))
    return g


def _finite_token(text):
    try:
        value = float(text)
    except ValueError:
        return False
    return bool(np.isfinite(value))


def _layout_error(path, language):
    raise SystemExit(_msg("pca_layout", language, path=path))


def read_plink19_eigenvec(path, ids, n_scores, *, language="en"):
    """Read a PLINK 1.9 ``.eigenvec`` and return scores in ``ids`` order.

    The file has no header. Each row is FID, IID, then scores, split on
    whitespace. Nothing else is skipped. Matching is on IID. Extra rows
    are ignored. The return value is ``(scores, n_ignored)`` with
    ``scores`` shaped ``(len(ids), n_scores)``.
    """
    if not os.path.isfile(path):
        raise SystemExit(_msg("pca_not_found", language, path=path))
    if isinstance(n_scores, bool) or not isinstance(n_scores, (int, np.integer)):
        raise SystemExit(_msg("pca_n_range", language, have="the file", n=n_scores))
    n_scores = int(n_scores)
    try:
        with open(path, "r", encoding="utf-8", newline="") as handle:
            raw_lines = handle.readlines()
    except OSError as exc:
        raise SystemExit(_msg("pca_not_found", language, path=path)) from exc
    if not raw_lines:
        raise SystemExit(_msg("pca_empty", language, path=path))
    parsed = []
    for lineno, line in enumerate(raw_lines, start=1):
        if line.strip() == "":
            raise SystemExit(_msg("pca_blank", language, path=path, line=lineno))
        parts = line.split()
        if lineno == 1:
            if line.lstrip().startswith("#") or len(parts) < 3 or any(
                not _finite_token(token) for token in parts[2:]
            ):
                _layout_error(path, language)
        if len(parts) < 3:
            raise SystemExit(_msg("pca_short", language, path=path, line=lineno))
        scores = parts[2:]
        if any(not _finite_token(token) for token in scores):
            raise SystemExit(_msg("pca_score", language, path=path, line=lineno))
        parsed.append((parts[1], scores, lineno))
    width = len(parsed[0][1])
    for _iid, scores, lineno in parsed[1:]:
        if len(scores) != width:
            raise SystemExit(_msg(
                "pca_width", language, path=path, line=lineno, got=len(scores), want=width,
            ))
    if n_scores < 1 or n_scores > width:
        raise SystemExit(_msg("pca_n_range", language, have=width, n=n_scores))
    by_iid = {}
    for iid, scores, _lineno in parsed:
        if iid in by_iid:
            raise SystemExit(_msg("pca_dup", language, path=path, iid=iid))
        by_iid[iid] = [float(token) for token in scores[:n_scores]]
    wanted = [str(iid) for iid in ids]
    for iid in wanted:
        if iid not in by_iid:
            raise SystemExit(_msg("pca_missing", language, path=path, iid=iid))
    id_set = set(wanted)
    n_ignored = sum(1 for iid in by_iid if iid not in id_set)
    scores = np.asarray([by_iid[iid] for iid in wanted], dtype=float)
    return scores, n_ignored


def _as_matrix(q, ids, *, language="en"):
    matrix = np.asarray(q, dtype=float)
    if matrix.ndim != 2:
        raise SystemExit(_msg("auto_groups_shape", language, shape=getattr(matrix, "shape", None)))
    id_list = [str(iid) for iid in ids]
    if len(id_list) != matrix.shape[0]:
        raise SystemExit(_msg(
            "auto_groups_ids", language, ids=len(id_list), rows=matrix.shape[0],
        ))
    seen = set()
    for iid in id_list:
        if iid in seen:
            raise SystemExit(_msg("auto_dup_id", language, iid=iid))
        seen.add(iid)
    if matrix.shape[0] > 0 and matrix.shape[1] < 1:
        raise SystemExit(_msg("auto_groups_shape", language, shape=matrix.shape))
    return matrix, id_list


def _tops(q):
    # argmax keeps the lowest index when two columns tie.
    index = np.argmax(q, axis=1)
    rows = np.arange(q.shape[0])
    values = q[rows, index]
    return index, values


def _column_name(index):
    return "C%d" % (int(index) + 1)


def relabel_first(raw_labels):
    """Name clusters G1, G2, ... by first appearance in input row order."""
    names = {}
    out = []
    next_id = 1
    for label in raw_labels:
        key = int(label)
        if key not in names:
            names[key] = "G%d" % next_id
            next_id += 1
        out.append(names[key])
    return out


def _parameters(method, *, k, cut, g, seed, dist, link, olo, input_kind, pca_n):
    if method == "major":
        return "k=%d;input=q" % int(k)
    if method == "threshold":
        return "cut=%s;k=%d;input=q" % (_compact(cut), int(k))
    if method == "hclust":
        body = "g=%d;dist=%s;linkage=%s;olo=%d;input=%s" % (
            int(g), dist, link, 1 if olo else 0, input_kind,
        )
    else:
        body = "g=%d;seed=%d;restarts=%d;input=%s" % (
            int(g), int(seed), KMEANS_RESTARTS, input_kind,
        )
    if input_kind == "pca":
        body += ";pca_n=%d" % int(pca_n)
    return body + ";k=%d" % int(k)


def _hclust_labels(data, g, dist, link, olo, explicit_cap, *, language="en"):
    n = int(data.shape[0])
    if n < 2:
        return ["G1"] * n
    cap = auto_hclust_cap(explicit_cap, n, language=language)
    # linkage_matrix checks the cap before SciPy builds the distance vector.
    z = linkage_matrix(data, dist, link, olo, language=language, max_bytes=cap)
    if z.shape[0] == 0:
        return ["G1"] * n
    from scipy.cluster.hierarchy import fcluster
    raw = fcluster(np.asarray(z, dtype=float), t=int(g), criterion="maxclust")
    found = len({int(label) for label in raw})
    if found != int(g):
        raise SystemExit(_msg("hclust_fewer", language, got=found, want=int(g)))
    return relabel_first(raw)


def _wcss(data, labels, centroid):
    diff = np.asarray(data, dtype=float) - np.asarray(centroid, dtype=float)[np.asarray(labels, dtype=int)]
    return float(np.einsum("ij,ij->", diff, diff))


def _kmeans_labels(data, g, seed, *, language="en", details=None):
    """Ten kmeans2 restarts from one Generator. No whitening.

    ``missing='raise'`` makes an empty cluster a failed restart. The kept
    run is the lowest within-cluster sum of squares. An equal sum keeps
    the earlier restart.
    """
    from scipy.cluster.vq import ClusterError, kmeans2
    work = np.array(data, dtype=float, copy=True, order="C")
    rng = np.random.default_rng(int(seed))
    best_labels = None
    best_wcss = None
    failed = 0
    for _restart in range(KMEANS_RESTARTS):
        try:
            centroid, label = kmeans2(
                work, int(g), minit="++", missing="raise", seed=rng,
            )
        except ClusterError:
            failed += 1
            continue
        label = np.asarray(label, dtype=int)
        if len(set(int(item) for item in label)) != int(g):
            failed += 1
            continue
        score = _wcss(work, label, centroid)
        if best_labels is None or score < best_wcss:
            best_labels = label.copy()
            best_wcss = score
    if details is not None:
        details["kmeans_whiten"] = "no"
        details["kmeans_failed_restarts"] = failed
        details["kmeans_restarts"] = KMEANS_RESTARTS
    if best_labels is None:
        raise SystemExit(_msg(
            "kmeans_all_failed", language, restarts=KMEANS_RESTARTS, failed=failed,
        ))
    return relabel_first(best_labels)


def auto_groups(q, ids, method, **params):
    """Return one ``(id, group, method, parameters, max_q, top_column)`` per row.

    ``major`` is ``C{c+1}`` for the lowest-index argmax. ``threshold`` uses
    that name unless ``max(q) < cut``, in which case the group is
    ``admixed``. ``hclust`` cuts ``linkage_matrix`` with
    ``fcluster(..., criterion='maxclust')``. ``kmeans`` is ten
    ``kmeans2`` restarts. ``hclust`` and ``kmeans`` are renamed ``G1``,
    ``G2``, ... by first appearance.

    ``data`` is an optional PCA matrix. It is used only by ``hclust`` and
    ``kmeans``. ``max_q`` and ``top_column`` always come from ``q``.
    ``max_bytes`` is the raw ``--hclust-max-bytes`` value (``None`` when
    the flag is omitted). ``details``, if a dict, receives cut and restart
    notes for the summary.
    """
    language = params.get("language", "en")
    if method not in CLUSTER_METHODS and method not in ("major", "threshold"):
        raise SystemExit(_msg("auto_groups_method", language, method=method))
    matrix, id_list = _as_matrix(q, ids, language=language)
    n = matrix.shape[0]
    k = int(params.get("k", matrix.shape[1]))
    cut = params.get("cut", 0.5)
    g = params.get("g", None)
    seed = int(params.get("seed", 0))
    dist = params.get("dist", "correlation")
    link = params.get("link", "average")
    olo = bool(params.get("olo", False))
    data = params.get("data", None)
    pca_n = params.get("pca_n", None)
    explicit_cap = params.get("max_bytes", None)
    details = params.get("details", None)
    input_kind = "q"
    cluster = matrix
    if data is not None:
        if method not in CLUSTER_METHODS:
            raise SystemExit(_msg("pca_needs_cluster", language))
        cluster = np.asarray(data, dtype=float)
        if cluster.ndim != 2 or cluster.shape[0] != n:
            raise SystemExit(_msg(
                "auto_pca_shape",
                language,
                rows=getattr(cluster, "shape", (None,))[0],
                want=n,
            ))
        if pca_n is None:
            raise SystemExit(_msg("pca_needs_n", language))
        if int(cluster.shape[1]) != int(pca_n):
            raise SystemExit(_msg(
                "auto_pca_n_mismatch", language, got=int(cluster.shape[1]), n=int(pca_n),
            ))
        input_kind = "pca"
    if method == "threshold":
        cut = check_admix_cut(cut, language=language)
    if method in CLUSTER_METHODS:
        g = check_auto_g_against_n(g, n, language=language)
    if n == 0:
        return []
    top_index, max_q = _tops(matrix)
    if method == "major":
        groups = [_column_name(index) for index in top_index]
    elif method == "threshold":
        groups = []
        for index, value in zip(top_index, max_q):
            if float(value) < float(cut):
                groups.append("admixed")
            else:
                groups.append(_column_name(index))
    elif method == "hclust":
        groups = _hclust_labels(
            cluster, g, dist, link, olo, explicit_cap, language=language,
        )
        if details is not None:
            details["hclust_cut"] = "fcluster maxclust"
    else:
        groups = _kmeans_labels(cluster, g, seed, language=language, details=details)
    parameters = _parameters(
        method, k=k, cut=cut, g=g, seed=seed, dist=dist, link=link, olo=olo,
        input_kind=input_kind, pca_n=pca_n,
    )
    rows = []
    for iid, group, index, value in zip(id_list, groups, top_index, max_q):
        rows.append((
            iid,
            group,
            method,
            parameters,
            float(value),
            _column_name(index),
        ))
    return rows


def write_groups_auto_tsv(path, rows):
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("\t".join(GROUPS_AUTO_COLUMNS) + "\n")
        for iid, group, method, parameters, max_q, top in rows:
            handle.write("%s\t%s\t%s\t%s\t%.6f\t%s\n" % (
                iid, group, method, parameters, float(max_q), top,
            ))


def _first_order(names):
    order = []
    seen = set()
    for name in names:
        if name not in seen:
            seen.add(name)
            order.append(name)
    return order


def contingency_lines(auto_names, known_names, rest_name):
    """Count table. Rows follow auto groups. Columns follow known groups.

    The rest name is always a column. When it never appears it is last.
    """
    if len(auto_names) != len(known_names):
        raise SystemExit(_msg(
            "auto_groups_ids", language="en", ids=len(known_names), rows=len(auto_names),
        ))
    columns = _first_order(known_names)
    if rest_name not in columns:
        columns.append(rest_name)
    rows = _first_order(auto_names)
    counts = {(auto, known): 0 for auto in rows for known in columns}
    for auto, known in zip(auto_names, known_names):
        counts[(auto, known)] += 1
    lines = [
        "contingency",
        "row_order\tauto groups in first-appearance order",
        "column_order\tknown groups in first-appearance order; rest name is included and is last when absent",
        "auto\t" + "\t".join(columns),
    ]
    for auto in rows:
        cells = [str(counts[(auto, known)]) for known in columns]
        lines.append(auto + "\t" + "\t".join(cells))
    return lines


def write_groups_auto_summary(
    path, rows, q, *, known_groups=None, rest_name="NA", details=None,
):
    matrix = np.asarray(q, dtype=float)
    details = details or {}
    if not rows:
        text = CIRCULAR_SENTENCE + "\n"
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        return
    method = rows[0][2]
    parameters = rows[0][3]
    k = matrix.shape[1]
    for part in parameters.split(";"):
        if part.startswith("k="):
            k = int(part.split("=", 1)[1])
            break
    order = _first_order(row[1] for row in rows)
    members = {name: [] for name in order}
    for index, row in enumerate(rows):
        members[row[1]].append(index)
    lines = [
        "method\t%s" % method,
        "auto_k\t%s" % k,
        "input\t%s" % ("pca" if "input=pca" in parameters else "q"),
        "parameters\t%s" % parameters,
        "n\t%d" % len(rows),
    ]
    if "eigenvec_rows_ignored" in details:
        lines.append("eigenvec_rows_ignored\t%d" % int(details["eigenvec_rows_ignored"]))
    if method == "hclust":
        lines.append("hclust_cut\t%s" % details.get("hclust_cut", "fcluster maxclust"))
    if method == "kmeans":
        lines.append("kmeans_whiten\t%s" % details.get("kmeans_whiten", "no"))
        lines.append("kmeans_restarts\t%d" % int(details.get("kmeans_restarts", KMEANS_RESTARTS)))
        lines.append(
            "kmeans_failed_restarts\t%d" % int(details.get("kmeans_failed_restarts", 0))
        )
    lines.append("group\tsize")
    for name in order:
        lines.append("%s\t%d" % (name, len(members[name])))
    header = ["group"] + [_column_name(index) for index in range(matrix.shape[1])]
    lines.append("mean_q\tK=%d" % matrix.shape[1])
    lines.append("\t".join(header))
    for name in order:
        mean = matrix[members[name]].mean(axis=0)
        cells = ["%.6f" % float(value) for value in mean]
        lines.append(name + "\t" + "\t".join(cells))
    lines.append(CIRCULAR_SENTENCE)
    if known_groups is not None:
        lines.extend(contingency_lines(
            [row[1] for row in rows], list(known_groups), rest_name,
        ))
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("\n".join(lines) + "\n")
