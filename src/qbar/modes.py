"""Group same-K replicates into modes.

The procedure is qbar's own. Column similarity follows the active
alignment method. Pairs are matched one-to-one by
``scipy.optimize.linear_sum_assignment``. A mode is a connected
component of pairs whose similarity is at least the cut. This is not
CLUMPAK's MCL (Kopelman et al. 2015, p. 1181), not pong's cliques at
0.97 (Behr et al. 2016, section 2.2), and not Clumppling's Louvain
(paper section 3.4). This module does not import PIL.

``seed`` is accepted and returned. These steps do not draw random numbers.
Permutations in the returned lists are 0-based. The TSV writer prints
them 1-based. K is the column count.
"""
from __future__ import annotations

import os

import numpy as np

from .align import (
    ALIGN_METHODS,
    JACCARD_SETS,
    jaccard_matrix,
    pearson_matrix,
    pong_sim,
)
from .messages import text as _msg


REPLICATE_COLUMNS = (
    "K",
    "replicate_file",
    "mode_id",
    "is_mode_rep",
    "sim_to_k_ref",
    "sim_to_mode_ref",
    "perm",
)


SUMMARY_COLUMNS = (
    "K",
    "n_replicates",
    "n_modes",
    "major_mode_id",
    "major_mode_size",
    "major_mode_mean_sim",
)


def require_replicate_flags(replicates, cut, language="en"):
    """Check ``--replicates`` and ``--mode-sim-cut`` together.

    The cut has no default. It is required only when replicates are on,
    and it is rejected when replicates are off. A cut that is used must
    lie in ``[0, 1]``.
    """
    if replicates and cut is None:
        raise SystemExit(_msg("replicates_requires_cut", language))
    if cut is not None and not replicates:
        raise SystemExit(_msg("mode_sim_cut_requires", language))
    if not replicates:
        return None
    return _check_cut(cut, language)


def _check_cut(cut, language):
    try:
        value = float(cut)
    except (TypeError, ValueError):
        raise SystemExit(_msg("mode_sim_cut_range", language, cut=cut))
    # NaN fails both comparisons. The message names the value that was passed.
    if not (0.0 <= value <= 1.0):
        raise SystemExit(_msg("mode_sim_cut_range", language, cut=cut))
    return value


def _column_similarity(left, right, method, jaccard_set, jaccard_cut):
    """K by K similarity of columns of ``left`` (rows) to ``right`` (columns)."""
    mask = np.ones(left.shape[0], dtype=bool)
    if method in ("greedy", "hungarian"):
        return pearson_matrix(left, right, mask)
    if method == "pong":
        sim = np.zeros((left.shape[1], right.shape[1]), dtype=float)
        for col in range(left.shape[1]):
            for other in range(right.shape[1]):
                sim[col, other] = pong_sim(left[:, col], right[:, other])
        return sim
    return jaccard_matrix(left, right, mask, kind=jaccard_set, cut=jaccard_cut)


def _assign(sim, language):
    """One-to-one column match maximising the sum of ``sim``.

    Returns the mean of the matched entries, and a permutation that
    places the column side into the row side's column order.
    """
    try:
        from scipy.optimize import linear_sum_assignment
    except ImportError as exc:
        raise SystemExit(_msg("replicate_needs_scipy", language)) from exc
    rows, cols = linear_sum_assignment(sim, maximize=True)
    by_row = {int(row): int(col) for row, col in zip(rows.tolist(), cols.tolist())}
    width = int(sim.shape[0])
    perm = [by_row[index] for index in range(width)]
    matched = [float(sim[index, perm[index]]) for index in range(width)]
    return float(np.mean(matched)), perm


def _invert_perm(perm):
    inverse = [0] * len(perm)
    for index, source in enumerate(perm):
        inverse[source] = index
    return inverse


def _median(values):
    return float(np.median(np.asarray(values, dtype=float)))


def _mode_sort_key(draft):
    """Larger modes first. Higher mean similarity next. NA ranks last. Then path."""
    mean_sim = draft["mean_sim"]
    if mean_sim is None:
        mean_key = (1, 0.0)
    else:
        mean_key = (0, -float(mean_sim))
    return (-draft["size"], mean_key, draft["min_path"])


def modes_for_k(matrices, method, cut, seed=0, jaccard_set="dominant", jaccard_cut=0.5, *, language="en"):
    """Group replicates that share one K.

    ``matrices`` is a list of ``(path, ndarray)``. Paths are sorted here,
    and ties keep the first path in that order. Every matrix must have
    the same shape. ``method`` is an alignment method name. ``cut`` is
    the pair-similarity link threshold in ``[0, 1]``.

    The returned dict includes ``major_mean_q``, the renormalised mean of
    the major mode, and ``rows`` in sorted path order.
    """
    if method not in ALIGN_METHODS:
        raise SystemExit(_msg(
            "replicate_method",
            language,
            methods=", ".join(ALIGN_METHODS),
            method=method,
        ))
    if method == "jaccard" and jaccard_set not in JACCARD_SETS:
        raise SystemExit(_msg(
            "replicate_jaccard_set",
            language,
            choices=", ".join(JACCARD_SETS),
            kind=jaccard_set,
        ))
    cut_value = _check_cut(cut, language)
    seed = int(seed)
    if not matrices:
        raise SystemExit(_msg("replicate_empty", language))
    items = sorted(matrices, key=lambda item: item[0])
    paths = [item[0] for item in items]
    arrays = [np.asarray(item[1], dtype=float) for item in items]
    shape = arrays[0].shape
    if len(shape) != 2:
        raise SystemExit(_msg("replicate_shape", language, path=paths[0]))
    for path, array in zip(paths, arrays):
        if array.shape != shape:
            raise SystemExit(_msg("replicate_shape", language, path=path))
    n = len(arrays)
    k_cols = int(shape[1])
    pair_sim = [{} for _ in range(n)]
    pair_perm = [{} for _ in range(n)]
    for left in range(n):
        for right in range(left + 1, n):
            sim = _column_similarity(
                arrays[left], arrays[right], method, jaccard_set, jaccard_cut,
            )
            score, perm_right = _assign(sim, language)
            pair_sim[left][right] = score
            pair_sim[right][left] = score
            pair_perm[left][right] = perm_right
            pair_perm[right][left] = _invert_perm(perm_right)
    if n == 1:
        ref = 0
    else:
        medians = [
            _median([pair_sim[index][other] for other in range(n) if other != index])
            for index in range(n)
        ]
        best = max(medians)
        ref = min(index for index, value in enumerate(medians) if value == best)
    parent = list(range(n))

    def find(index):
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left, right):
        root_left = find(left)
        root_right = find(right)
        if root_left == root_right:
            return
        if root_left < root_right:
            parent[root_right] = root_left
        else:
            parent[root_left] = root_right

    for left in range(n):
        for right in range(left + 1, n):
            if pair_sim[left][right] >= cut_value:
                union(left, right)
    grouped = {}
    for index in range(n):
        grouped.setdefault(find(index), []).append(index)
    drafts = []
    for members in grouped.values():
        vals = [
            pair_sim[left][right]
            for offset, left in enumerate(members)
            for right in members[offset + 1:]
        ]
        mean_sim = None if not vals else float(np.mean(np.asarray(vals, dtype=float)))
        drafts.append({
            "members": members,
            "size": len(members),
            "mean_sim": mean_sim,
            "min_path": paths[members[0]],
        })
    drafts.sort(key=_mode_sort_key)

    def choose_ref(members):
        if len(members) == 1:
            return members[0]
        medians = []
        for member in members:
            others = [pair_sim[member][other] for other in members if other != member]
            medians.append(_median(others))
        best_median = max(medians)
        for member, value in zip(members, medians):
            if value == best_median:
                return member
        return members[0]

    modes = []
    mode_id_of = [None] * n
    mode_ref_of = [None] * n
    perm_of = [None] * n
    for mode_number, draft in enumerate(drafts, start=1):
        members = draft["members"]
        mode_ref = choose_ref(members)
        for member in members:
            if member == mode_ref:
                perm_of[member] = list(range(k_cols))
            else:
                perm_of[member] = list(pair_perm[mode_ref][member])
            mode_id_of[member] = mode_number
            mode_ref_of[member] = mode_ref
        aligned = [arrays[member][:, perm_of[member]] for member in members]
        mean = np.mean(np.stack(aligned, axis=0), axis=0)
        sums = mean.sum(axis=1)
        if np.any(sums == 0.0):
            raise SystemExit(_msg(
                "mode_mean_zero_row", language, mode=mode_number, k=k_cols,
            ))
        mean = mean / sums[:, None]
        modes.append({
            "mode_id": mode_number,
            "size": len(members),
            "mean_sim": draft["mean_sim"],
            "reference": paths[mode_ref],
            "members": [paths[member] for member in members],
            "mean_q": mean,
        })
    rows = []
    for index, path in enumerate(paths):
        mode_ref = mode_ref_of[index]
        rows.append({
            "path": path,
            "mode_id": mode_id_of[index],
            "is_mode_rep": index == mode_ref,
            "sim_to_k_ref": None if index == ref else pair_sim[index][ref],
            "sim_to_mode_ref": None if index == mode_ref else pair_sim[index][mode_ref],
            "perm": perm_of[index],
        })
    pair_similarity = {}
    pair_perm_by_path = {}
    for left, path in enumerate(paths):
        pair_similarity[path] = {}
        pair_perm_by_path[path] = {}
        for right, other in enumerate(paths):
            if left == right:
                continue
            pair_similarity[path][other] = pair_sim[left][right]
            pair_perm_by_path[path][other] = list(pair_perm[left][right])
    major = modes[0]
    return {
        "seed": seed,
        "k": k_cols,
        "reference": paths[ref],
        "n_replicates": n,
        "n_modes": len(modes),
        "major_mode_id": major["mode_id"],
        "major_mode_size": major["size"],
        "major_mode_mean_sim": major["mean_sim"],
        "major_mean_q": major["mean_q"],
        "rows": rows,
        "modes": modes,
        "pair_similarity": pair_similarity,
        "pair_perm": pair_perm_by_path,
    }


def assemble_replicates(loaded, method, cut, seed=0, jaccard_set="dominant", jaccard_cut=0.5, *, language="en"):
    """Build the matrices that across-K alignment will see.

    ``loaded`` is ``(path, ndarray, k)`` in collect order. A K with one
    file keeps that array and is omitted from the report map. A K with
    two or more files contributes its major-mode mean. ``src_paths[k]``
    lists the paths for ``args.txt``, sorted when that K has several files.
    """
    _check_cut(cut, language)
    by_k = {}
    order = []
    for path, matrix, k in loaded:
        if k not in by_k:
            order.append(k)
            by_k[k] = []
        by_k[k].append((path, matrix))
    q_by_k = {}
    src_paths = {}
    reports = {}
    for k in order:
        items = sorted(by_k[k], key=lambda item: item[0])
        src_paths[k] = [path for path, _matrix in items]
        if len(items) == 1:
            q_by_k[k] = items[0][1]
            continue
        report = modes_for_k(
            items, method, cut, seed=seed,
            jaccard_set=jaccard_set, jaccard_cut=jaccard_cut,
            language=language,
        )
        q_by_k[k] = report["major_mean_q"]
        reports[k] = report
    return q_by_k, src_paths, reports


def _fmt_sim(value):
    if value is None:
        return "NA"
    return "%.6f" % float(value)


def _write_mean_q(path, matrix):
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        for row in np.asarray(matrix, dtype=float):
            handle.write(" ".join("%.6f" % float(value) for value in row) + "\n")


def write_replicate_outputs(outdir, reports):
    """Write replicate tables and one Q file per mode.

    ``reports`` maps K to a ``modes_for_k`` result. An empty map writes
    nothing. Minor modes are written, not dropped.
    """
    if not reports:
        return []
    written = []
    summary = os.path.join(outdir, "replicates_summary.tsv")
    with open(summary, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("\t".join(SUMMARY_COLUMNS) + "\n")
        for k in sorted(reports):
            report = reports[k]
            handle.write("%d\t%d\t%d\t%d\t%d\t%s\n" % (
                k,
                report["n_replicates"],
                report["n_modes"],
                report["major_mode_id"],
                report["major_mode_size"],
                _fmt_sim(report["major_mode_mean_sim"]),
            ))
    written.append(summary)
    for k in sorted(reports):
        report = reports[k]
        table = os.path.join(outdir, "replicates_K%d.tsv" % k)
        with open(table, "w", encoding="utf-8", newline="\n") as handle:
            handle.write("\t".join(REPLICATE_COLUMNS) + "\n")
            for row in report["rows"]:
                perm = ",".join(str(int(index) + 1) for index in row["perm"])
                handle.write("%d\t%s\t%d\t%s\t%s\t%s\t%s\n" % (
                    k,
                    row["path"],
                    row["mode_id"],
                    "yes" if row["is_mode_rep"] else "no",
                    _fmt_sim(row["sim_to_k_ref"]),
                    _fmt_sim(row["sim_to_mode_ref"]),
                    perm,
                ))
        written.append(table)
        for mode in report["modes"]:
            q_path = os.path.join(
                outdir, "mode_mean_K%d_mode%d.Q" % (k, mode["mode_id"]),
            )
            _write_mean_q(q_path, mode["mean_q"])
            written.append(q_path)
    return written
