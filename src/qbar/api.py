"""Programmatic entry point.

``run`` accepts the namespace from ``build_parser``. K is the column
count. Permutations are 0-based in the returned arrays and 1-based in
the TSV files.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import platform
import subprocess
import sys
from dataclasses import asdict, dataclass, is_dataclass

import numpy as np

from .align import align_qs
from .bootstrap import bootstrap_support, write_match_support
from .permtest import permutation_columns
from .io import (
    check_shapes,
    collect_q,
    k_of,
    load_groups,
    load_ids,
    load_q_set,
    parse_colors,
    read_q,
)
from .logs import (
    check_logs_map,
    collect_logs,
    parse_admixture_log,
    write_cv_loglik_tsv,
)
from .autogroups import (
    auto_groups,
    check_auto_g_against_n,
    read_plink19_eigenvec,
    validate_auto_flags,
    write_groups_auto_summary,
    write_groups_auto_tsv,
)
from .flow import check_consecutive_k, cluster_flow, write_cluster_flow_tsv
from .lowconf import append_low_confidence_rows, read_low_confidence_table
from .messages import text as _msg
from .modes import assemble_replicates, require_replicate_flags, write_replicate_outputs
from .selectk import select_k_table, write_select_k_tsv, write_select_k_txt
from .order import (
    WITHIN,
    apply_order_mode,
    check_hclust_opts,
    validate_order_flags,
    write_linkage_index,
    write_linkage_tsv,
)
from .parentshare import (
    check_parent_alpha,
    parent_interval_rows,
    write_parent_share_ci,
)
from .report import column_label, write_align_compare, write_align_report, write_tables


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


def legend_lines(q, groups, owners, hexes):
    rows = []
    for c, hx in enumerate(hexes):
        rows.append((hx, "C%d %s" % (c + 1, column_label(owners[c], q, groups, c))))
    return rows


def parse_within(items, *, language="en"):
    out = {}
    for item in items or []:
        if "=" not in item:
            raise SystemExit(_msg("within_group_syntax", language, item=item))
        name, mode = item.split("=", 1)
        mode = mode.strip()
        if mode not in WITHIN:
            raise SystemExit(_msg("within_mode", language, modes=", ".join(WITHIN), mode=mode))
        out[name.strip()] = mode
    return out


@dataclass
class RunResult:
    """Values this run already computed.

    K is the column count. ``permutations[K]`` is the 0-based raw-column
    order: position i holds the raw column drawn as aligned column i.
    The same order is written 1-based in ``perm_K{K}.tsv``. ``colours[K]``
    lists the hex colours in that aligned order. ``paths`` lists files
    written, in write order.
    """

    aligned: dict[int, np.ndarray]
    permutations: dict[int, list[int]]
    order: list[int]
    spans: list[dict[str, object]]
    colours: dict[int, list[str]]
    paths: list[str]


def _json_ready(value):
    """Return a JSON value. Namespace and dataclass keys are sorted."""
    if value is None or isinstance(value, (bool, str, int, float)):
        return value
    if isinstance(value, os.PathLike):
        return os.fspath(value)
    if isinstance(value, argparse.Namespace):
        return {key: _json_ready(item) for key, item in sorted(vars(value).items())}
    if is_dataclass(value) and not isinstance(value, type):
        raw = asdict(value)
        return {key: _json_ready(raw[key]) for key in sorted(raw)}
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    raise TypeError("run.json cannot store %s" % type(value).__name__)


def write_run_json(path, payload):
    """Write ``payload`` as UTF-8 JSON, indent 2, with a trailing newline.

    Keys stay in the given order. ``sort_keys`` is not used. Namespace
    and dataclass values are stored as objects.
    """
    data = _json_ready(payload)
    text = json.dumps(data, indent=2, ensure_ascii=False, sort_keys=False, allow_nan=False)
    if not text.endswith("\n"):
        text += "\n"
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def _git_stdout(root, cmd, env):
    try:
        proc = subprocess.run(
            cmd,
            cwd=root,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    try:
        return proc.stdout.decode("ascii")
    except UnicodeError:
        return None


def _git_commit():
    """HEAD if this file is tracked in the checkout that contains it.

    Otherwise ``unknown``. The hash is the stdout of ``git rev-parse HEAD``
    and is kept only when it is 40 hex characters.
    """
    code_path = os.path.realpath(__file__)
    directory = os.path.dirname(code_path)
    root = None
    while True:
        if os.path.exists(os.path.join(directory, ".git")):
            root = directory
            break
        parent = os.path.dirname(directory)
        if parent == directory:
            return "unknown"
        directory = parent
    rel = os.path.relpath(code_path, root)
    if rel == ".." or rel.startswith(".." + os.sep):
        return "unknown"
    env = os.environ.copy()
    for key in (
        "GIT_DIR",
        "GIT_WORK_TREE",
        "GIT_INDEX_FILE",
        "GIT_OBJECT_DIRECTORY",
        "GIT_NAMESPACE",
    ):
        env.pop(key, None)
    env["GIT_TERMINAL_PROMPT"] = "0"
    if _git_stdout(root, ["git", "ls-files", "--error-unmatch", "--", rel], env) is None:
        return "unknown"
    text = _git_stdout(root, ["git", "rev-parse", "HEAD"], env)
    if text is None:
        return "unknown"
    commit = text.strip()
    if len(commit) == 40 and all(ch in "0123456789abcdef" for ch in commit):
        return commit
    return "unknown"


def _file_record(path):
    digest = hashlib.sha256()
    size = 0
    with open(path, "rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
            size += len(chunk)
    return {"path": path if isinstance(path, str) else os.fspath(path), "sha256": digest.hexdigest(), "nbytes": size}


def _input_records(q_paths, args, extra_paths=None):
    paths = list(q_paths)
    for path in (
        args.fam, args.ids, args.ind, args.groups, args.order_file, args.color_file,
        getattr(args, "pca", None),
    ):
        if path:
            paths.append(path)
    if extra_paths:
        for path in extra_paths:
            if path:
                paths.append(path)
    return [_file_record(path) for path in paths]


def _resolved_options(args):
    ready = {}
    for key in sorted(vars(args)):
        ready[key] = _json_ready(getattr(args, key))
    return ready


def _qbar_version():
    module = sys.modules.get("qbar")
    version = getattr(module, "__version__", None) if module is not None else None
    if isinstance(version, str):
        return version
    from . import __version__
    return __version__


def _dependency_versions():
    import PIL
    import scipy
    return {
        "numpy": np.__version__,
        "scipy": scipy.__version__,
        "pillow": PIL.__version__,
        "python": platform.python_version(),
    }


def _provenance_payload(args, argv, q_paths, started, extra_paths=None):
    versions = _dependency_versions()
    if argv is None:
        used = list(sys.argv[1:])
    else:
        used = list(argv)
    return {
        "qbar_version": _qbar_version(),
        "git_commit": _git_commit(),
        "argv": [str(item) for item in used],
        "resolved_options": _resolved_options(args),
        "inputs": _input_records(q_paths, args, extra_paths),
        "numpy": versions["numpy"],
        "scipy": versions["scipy"],
        "pillow": versions["pillow"],
        "python": versions["python"],
        "started": started,
        "platform": platform.platform(),
    }


def _bootstrap_request(args, language):
    """Return ``(n_boot, seed)``. Seed is checked only when ``n_boot`` > 0."""
    n_boot = getattr(args, "bootstrap", 0)
    if isinstance(n_boot, bool) or not isinstance(n_boot, (int, np.integer)) or int(n_boot) < 0:
        raise SystemExit(_msg("bootstrap_negative", language, n=n_boot))
    n_boot = int(n_boot)
    if n_boot == 0:
        return 0, 0
    seed = getattr(args, "bootstrap_seed", 0)
    if isinstance(seed, bool) or not isinstance(seed, (int, np.integer)) or int(seed) < 0:
        raise SystemExit(_msg("bootstrap_seed_negative", language, seed=seed))
    return n_boot, int(seed)


def _perm_request(args, language):
    """Return ``(n_perm, seed, null)``. Seed and null are checked only when ``n_perm`` > 0."""
    n_perm = getattr(args, "perm", 0)
    if isinstance(n_perm, bool) or not isinstance(n_perm, (int, np.integer)) or int(n_perm) < 0:
        raise SystemExit(_msg("perm_negative", language, n=n_perm))
    n_perm = int(n_perm)
    if n_perm == 0:
        return 0, 0, None
    seed = getattr(args, "perm_seed", 0)
    if isinstance(seed, bool) or not isinstance(seed, (int, np.integer)) or int(seed) < 0:
        raise SystemExit(_msg("perm_seed_negative", language, seed=seed))
    null = getattr(args, "perm_null", None)
    if null is None:
        raise SystemExit(_msg("perm_null_required", language))
    if null not in ("rows", "column"):
        raise SystemExit(_msg("perm_null_choice", language, null=null))
    return n_perm, int(seed), null


def _parent_request(args, language, n_boot, n_perm):
    """Return ``(parent_ci, parent_test, alpha)``.

    Alpha is checked even when both flags are off. The default 0.05
    passes. ``--parent-ci`` requires ``n_boot`` > 0. ``--parent-test``
    requires ``n_perm`` > 0. A missing ``--perm-null`` is still reported
    by ``_perm_request`` before this function runs.
    """
    parent_ci = bool(getattr(args, "parent_ci", False))
    parent_test = bool(getattr(args, "parent_test", False))
    alpha = check_parent_alpha(getattr(args, "parent_alpha", 0.05), language)
    if parent_ci and n_boot <= 0:
        raise SystemExit(_msg("parent_ci_needs_bootstrap", language))
    if parent_test and n_perm <= 0:
        raise SystemExit(_msg("parent_test_needs_perm", language))
    return parent_ci, parent_test, alpha


def _na_support_rows(perm, meta, method):
    """ST1 columns when bootstrap did not run. Counts and the bootstrap seed are NA."""
    rows = []
    for k_to in sorted(meta):
        for index, raw in enumerate(perm[k_to]):
            rows.append({
                "K_to": int(k_to),
                "aligned_column": "C%d" % (index + 1),
                "raw_column": int(raw) + 1,
                "n_boot": "NA",
                "n_same": "NA",
                "support": "NA",
                "seed": "NA",
                "method": method,
                "n_empty_mask": "NA",
            })
    return rows


def _attach_permutation(rows, aligned, q_by_k, meta, method, n_perm, seed, null, *,
                        groups, align_mode, align_groups, qmax, jaccard_set, jaccard_cut,
                        language):
    """Append permutation fields. One K step is rerun, not the whole chain."""
    stats = []
    for k_to in sorted(meta):
        # q_prev is the aligned matrix from the full-data run, anchor included.
        stats.extend(permutation_columns(
            aligned[k_to - 1],
            q_by_k[k_to],
            method,
            n_perm,
            seed,
            null,
            groups=groups,
            align_mode=align_mode,
            align_groups=align_groups,
            qmax=qmax,
            jaccard_set=jaccard_set,
            jaccard_cut=jaccard_cut,
            language=language,
        ))
    if len(stats) != len(rows):
        raise SystemExit(_msg("perm_internal", language))
    for row, item in zip(rows, stats):
        row.update(item)


def run(args: argparse.Namespace, argv: list[str] | None = None) -> RunResult:
    """Run one plot from a parsed command line.

    ``args`` is the ``argparse.Namespace`` from ``build_parser``.
    Attribute names are that parser's option dests. A mapping is not
    accepted.

    K is the column count. Permutations are 0-based in ``permutations``
    and 1-based in the ``perm_K`` TSV files.

    ``argv`` is what ``args.txt`` records. ``None`` uses ``sys.argv``,
    the same choice ``main`` makes when it is called without argv.
    A list is written as the word ``qbar`` followed by that list.
    When ``args.provenance`` is true, ``run.json`` is written after
    ``args.txt``. Its ``argv`` is the list passed in, or ``sys.argv[1:]``
    when ``argv`` is ``None``.

    ``args.q_format`` selects the matrix layout: ``admixture``, ``meanq``,
    or ``qopt``. ``args.ind`` is an optional EIGENSTRAT .ind path. At most
    one of fam, ids, and ind is set. ``args.language`` is ``en`` or ``zh``.
    Help, errors, and warnings use ``en`` unless it is ``zh``.

    When ``args.logs`` is set, ADMIXTURE stdout is parsed and
    ``cv_loglik.tsv``, ``cv_loglik.png``, and ``cv_loglik.pdf`` are written.
    When it is omitted, those files are not written. ``args.logs_map``
    checks log and Q pairs and does not add a column.

    When ``args.select_k`` is set, the CV and log-likelihood rows are
    summarised into ``select_k.tsv``, ``select_k.txt``, ``select_k.png``,
    and ``select_k.pdf``. The flag requires ``args.logs``. When it is
    omitted, those files are not written. The barplot K list is the Q
    files and does not change because of this report.

    When ``args.replicates`` is set, several Q files may share one K.
    They are grouped into modes, and the major-mode mean is what the
    existing alignment sees. ``args.mode_sim_cut`` is required in that
    case and has no default. When every K has one file, no
    ``replicates_`` file is written and the matrices passed onward are
    the loaded ones. Without ``args.replicates``, two files at one K
    still raise the duplicate-K error.

    When ``args.align_compare`` is set and there is at least one alignment
    step, ``align_compare.tsv`` and ``align_compare.txt`` are written.
    The chosen alignment is unchanged. The text does not declare a better method.

    When ``args.bootstrap`` is greater than 0 and this run aligned at least
    one K to K+1 step, individuals are resampled and ``match_support.tsv``
    is written. The default 0 writes no file and does not draw a seed.
    ``args.bootstrap_seed`` is used only when the count is greater than 0.
    The matrices are the ones alignment used. With ``args.replicates``,
    that is one matrix per K: the major-mode mean when that K had two or
    more files, otherwise the loaded matrix.

    When ``args.perm`` is greater than 0 and this run aligned at least one
    K to K+1 step, ``match_support.tsv`` also carries ``n_perm``,
    ``n_extreme``, ``p``, ``null``, and ``zero_column``. ``args.perm_null``
    is required then and is ``rows`` or ``column``. The default 0 adds no
    columns and does not draw a seed. If bootstrap is 0, the bootstrap
    columns ``n_boot``, ``n_same``, ``support``, ``seed``, and
    ``n_empty_mask`` are NA. ``rows`` shuffles the K+1 matrix and reruns
    that one match. ``column`` shuffles the matched new column and
    recomputes its similarity. The null name is written on every row.

    When ``args.parent_ci`` is set, ``parent_share_ci.tsv`` carries a
    percentile interval for the largest parent share of each new column.
    The default is off. The flag requires ``args.bootstrap`` greater
    than 0. The interval uses the row-index vectors that bootstrap
    already drew. It does not draw another set and does not align
    again. ``args.parent_alpha`` defaults to 0.05 and must lie strictly
    between 0 and 1.

    When ``args.parent_test`` is set, the same file carries
    ``p_one_parent``. The default is off. The flag requires
    ``args.perm`` greater than 0 and uses ``args.perm`` and
    ``args.perm_seed``. ``args.perm_null`` is still required whenever
    ``args.perm`` is greater than 0, because that rule belongs to the
    match permutation. The parent test does not use the null. Columns
    for a flag that is off are NA. Either flag writes the file when
    this run aligned at least one K to K+1 step. Both off writes no
    ``parent_share_ci.tsv``. ``match_support.tsv`` is unchanged by
    these flags except through the bootstrap or permutation they require.

    When ``args.low_confidence_table`` is set and this run writes
    ``align_report.txt``, rows for ``args.align_method`` are copied onto
    the end of that file. The table does not change the low-confidence
    cut. If the method has no rows, a warning is written and the file
    is left as the report alone. If the table is set and no alignment
    report is written, a warning says the table is unused. The default
    is omitted, which does not read a table and does not add a warning.

    When ``args.cluster_flow`` is ``sankey``, the run writes
    ``cluster_flow.tsv``, ``cluster_flow.png``, and ``cluster_flow.pdf``.
    The default ``none`` writes none of them. ``args.flow_weight`` is
    ``share`` or ``jaccard`` and defaults to ``share``. Setting it to
    something other than ``share`` while ``cluster_flow`` is ``none`` is
    an error. ``share`` is ``parent_shares`` of each destination column
    on the alignment mask. ``jaccard`` is the member-set Jaccard, using
    ``args.jaccard_set`` and ``args.jaccard_cut``. The figure axis title
    is ``membership weight``. ``low_confidence`` on an edge is the
    destination column's flag from the alignment report when that report
    is written, and NA otherwise. ``--no-align`` with ``sankey`` is an
    error. A gap in K is reported first.     No HTML flow file is written.

    When ``args.auto_groups`` is ``none`` (the default), the run writes no
    ``groups_auto.tsv`` and no ``groups_auto_summary.txt``. ``major``,
    ``threshold``, ``hclust``, and ``kmeans`` write both. Those groups do
    not replace ``args.groups`` in the figure order. ``--auto-k`` selects
    the aligned matrix and defaults to the largest K. ``threshold`` uses
    ``--admix-cut``, which must be above 0 and at most 1 (default 0.5).
    A row is admixed only when its maximum is below the cut. ``hclust``
    and ``kmeans`` require ``--auto-g``. ``kmeans`` keeps the lowest
    within-cluster sum of squares among 10 restarts from one Generator
    seeded by ``--auto-seed`` (default 0). ``--pca`` with a required
    ``--pca-n`` is a PLINK 1.9 eigenvec (no header; FID, IID, then scores)
    and is accepted only by ``hclust`` and ``kmeans``. A non-default auto
    flag while ``--auto-groups`` is ``none`` is an error. ``hclust`` on
    every row uses the same byte cap as an all-rows tree: 4294967296 when
    ``--hclust-max-bytes`` is omitted.

    ``--order-mode within`` (the default) orders inside groups and writes no
    linkage file. ``global-hclust`` clusters every row at ``--hclust-k`` and
    writes ``linkage_global.tsv`` when that order is one tree.
    ``group-hclust`` keeps each group contiguous. ``--group-order hclust``
    orders groups by the mean Q row and writes ``linkage_between_groups.tsv``.
    ``--within hclust`` in that mode also writes ``linkage_group_<n>.tsv`` for
    each group of at least two rows, with ``n`` the 1-based input index.
    Either of those group files causes ``linkage_index.tsv`` to be written.
    ``--dendrogram top`` draws the tree above the bars and may make those
    figures taller. The default ``none`` does not. When ``--hclust-max-bytes``
    is omitted, the all-rows vector and the between-group vector refuse above
    4294967296 bytes before the distance vector is built. Within-group trees
    stay uncapped unless a byte value is set. ``0`` means no cap. A refusal
    writes no output file.

    ``args.palette`` chooses bar colours. The default ``science`` is eight
    hex values sampled from Fig. 1D of Dong et al. 2023, Science 379:892,
    DOI 10.1126/science.add8655, then classic colours that are not already
    used, then ``hsv_hex``. ``classic`` is the previous 20 colours and
    restores the previous bar colours. ``tab10``, ``set1``, ``dark2``, and
    ``paired`` follow the same continuation. ``args.color_lock`` defaults
    to ``off``. ``on`` keeps the colour column c got at the lowest K,
    unless ``--color`` sets that column. ``args.greyscale_preview`` defaults
    to off and writes ``panel_grey.png``.
    """
    if args.provenance:
        started = datetime.datetime.now().astimezone().isoformat()
    else:
        started = None
    # Imported on call so this module can be imported without the drawing code.
    from .plot_static import (
        PALETTE_NAMES, ancestry_image, assign_colors, render, write_cv_loglik_plot,
        write_select_k_plot, write_cluster_flow_plot, write_greyscale_png,
    )

    language = args.language
    palette_name = getattr(args, "palette", "science")
    color_lock = getattr(args, "color_lock", "off")
    greyscale = bool(getattr(args, "greyscale_preview", False))
    if palette_name not in PALETTE_NAMES:
        raise SystemExit(_msg("palette_choice", language, name=palette_name))
    if color_lock not in ("off", "on"):
        raise SystemExit(_msg("color_lock_choice", language, mode=color_lock))
    flow_mode = getattr(args, "cluster_flow", "none")
    flow_weight = getattr(args, "flow_weight", "share")
    if flow_mode not in ("none", "sankey"):
        raise SystemExit(_msg("flow_mode_choice", language, mode=flow_mode))
    if flow_weight not in ("share", "jaccard"):
        raise SystemExit(_msg("flow_weight_choice", language, weight=flow_weight))
    # A non-default weight with the flow left off is an error. The default
    # share is not an error, including when the user passes it explicitly.
    if flow_mode != "sankey" and flow_weight != "share":
        raise SystemExit(_msg("flow_weight_needs_sankey", language, weight=flow_weight))
    auto_method = getattr(args, "auto_groups", "none")
    auto_k_arg = getattr(args, "auto_k", None)
    admix_cut = getattr(args, "admix_cut", 0.5)
    auto_g = getattr(args, "auto_g", None)
    auto_seed = getattr(args, "auto_seed", 0)
    pca_path = getattr(args, "pca", None)
    pca_n = getattr(args, "pca_n", None)
    # A non-default auto flag with --auto-groups none is an error. Passing
    # the stored defaults is not. Same rule as --flow-weight above.
    validate_auto_flags(
        auto_method, auto_k_arg, admix_cut, auto_g, auto_seed, pca_path, pca_n,
        language=language,
    )
    table_path = getattr(args, "low_confidence_table", None)
    table_rows = None
    if table_path is not None:
        table_rows = read_low_confidence_table(table_path, language=language)
    n_boot, boot_seed = _bootstrap_request(args, language)
    n_perm, perm_seed, perm_null = _perm_request(args, language)
    parent_ci, parent_test, parent_alpha = _parent_request(args, language, n_boot, n_perm)
    check_hclust_opts(args.hclust_dist, args.hclust_linkage, language=language)
    order_mode = getattr(args, "order_mode", "within")
    group_order = getattr(args, "group_order", "input")
    dendrogram_mode = getattr(args, "dendrogram", "none")
    explicit_cap = getattr(args, "hclust_max_bytes", None)
    # Flag errors happen before any output file is created.
    validate_order_flags(
        order_mode, group_order, dendrogram_mode, explicit_cap, args.order_file,
        language=language,
    )
    logs = getattr(args, "logs", None)
    logs_map = getattr(args, "logs_map", None)
    select_k = bool(getattr(args, "select_k", False))
    plateau_fraction = getattr(args, "plateau_fraction", 0.05)
    log_paths = None
    log_rows = None
    if select_k and not logs:
        raise SystemExit(_msg("select_k_requires", language))
    if logs_map and not logs:
        raise SystemExit(_msg("logs_map_requires", language))
    replicates_on = bool(getattr(args, "replicates", False))
    mode_sim_cut = getattr(args, "mode_sim_cut", None)
    require_replicate_flags(replicates_on, mode_sim_cut, language)
    if logs:
        log_paths = collect_logs(logs, language=language)
        if logs_map:
            check_logs_map(logs_map, log_paths, language=language)
        log_rows = []
        for log_path in log_paths:
            log_rows.extend(parse_admixture_log(log_path, language=language))
    files = collect_q(args.q, format=args.q_format, language=language)
    loaded = None
    if replicates_on:
        loaded = []
        for path in files:
            matrix = read_q(path, format=args.q_format, language=language)
            k_value = k_of(path, matrix, format=args.q_format, language=language)
            loaded.append((path, matrix, k_value))
    else:
        q_by_k, src = load_q_set(files, format=args.q_format, language=language)
    iids = load_ids(args.fam, args.ids, ind=args.ind, language=language)
    if replicates_on:
        for _path, matrix, k_value in loaded:
            check_shapes({k_value: matrix}, len(iids), language=language)
        q_by_k, src_paths, replicate_reports = assemble_replicates(
            loaded, args.align_method, mode_sim_cut, seed=0,
            jaccard_set=args.jaccard_set, jaccard_cut=args.jaccard_cut,
            language=language,
        )
    else:
        check_shapes(q_by_k, len(iids), language=language)
        src_paths = {k_value: [src[k_value]] for k_value in src}
        replicate_reports = {}
    groups = load_groups(args.groups, iids, args.id_col, args.group_col, args.rest_name, language=language)
    within_group = parse_within(args.within_group, language=language)
    unknown = sorted(set(within_group) - set(groups))
    if unknown:
        print(_msg("within_group_missing", language, names=", ".join(unknown)), file=sys.stderr)
    blocks = [x.strip() for x in args.blocks.split(",") if x.strip()] if args.blocks else []
    align_groups = [x.strip() for x in args.align_groups.split(",") if x.strip()]
    do_align = (len(q_by_k) > 1) if args.align is None else args.align
    # Name a missing K before the alignment requirement. Consecutive K
    # with --no-align then stops, because the flow needs that alignment.
    if flow_mode == "sankey" and args.align is False:
        check_consecutive_k(q_by_k, language=language)
        raise SystemExit(_msg("flow_needs_align", language))
    aligned, perm, meta = align_qs(
        q_by_k, groups, args.anchor_group.strip(), args.align_mode,
        align_groups, args.qmax, do_align, args.align_method,
        args.jaccard_set, args.jaccard_cut, language=language,
    )
    if flow_mode == "sankey":
        check_consecutive_k(aligned, language=language)
    ks = sorted(aligned)
    sort_k = args.sort_k or ks[-1]
    hclust_k = args.hclust_k or sort_k
    for name, k in (("--sort-k", sort_k), ("--hclust-k", hclust_k)):
        if k not in aligned:
            raise SystemExit(_msg("missing_q_for_k", language, name=name, k=k))
    if args.sort_col is not None and (args.sort_col < 1 or args.sort_col > sort_k):
        raise SystemExit(_msg("sort_col_range", language, k=sort_k))
    if args.order_file and blocks:
        print(_msg("order_file_ignores_blocks", language), file=sys.stderr)
    if order_mode != "within" and blocks:
        print(_msg("blocks_ignored", language, mode=order_mode), file=sys.stderr)
    if order_mode == "global-hclust" and (args.within != "iid" or within_group):
        print(_msg("within_ignored_global", language), file=sys.stderr)
    hc = {
        "dist": args.hclust_dist,
        "link": args.hclust_linkage,
        "olo": args.hclust_olo,
        "pre": args.hclust_pre,
    }
    # Auto groups, including the all-rows byte cap, finish before outdir exists.
    # The figure still orders by the known groups, not by these labels.
    auto_rows = None
    auto_details = {}
    auto_q = None
    if auto_method != "none":
        if auto_k_arg is None:
            auto_k = ks[-1]
        else:
            auto_k = auto_k_arg
            if auto_k not in aligned:
                raise SystemExit(_msg("auto_k_missing", language, k=auto_k))
        auto_q = aligned[auto_k]
        if auto_method in ("hclust", "kmeans"):
            check_auto_g_against_n(auto_g, auto_q.shape[0], language=language)
        pca_data = None
        if pca_path:
            pca_scores, n_ignored = read_plink19_eigenvec(
                pca_path, iids, pca_n, language=language,
            )
            pca_data = pca_scores
            auto_details["eigenvec_rows_ignored"] = n_ignored
        if auto_method == "hclust" and getattr(args, "hclust_pre", "none") != "none":
            print(_msg("hclust_pre_ignored", language), file=sys.stderr)
        auto_rows = auto_groups(
            auto_q,
            iids,
            auto_method,
            cut=admix_cut,
            g=auto_g,
            seed=auto_seed,
            dist=args.hclust_dist,
            link=args.hclust_linkage,
            olo=args.hclust_olo,
            max_bytes=explicit_cap,
            data=pca_data,
            pca_n=pca_n,
            k=auto_k,
            language=language,
            details=auto_details,
        )
    # Ordering, including the byte cap, finishes before outdir is created.
    arranged = apply_order_mode(
        iids, groups, blocks, args.within, within_group, args.rest_name,
        aligned[sort_k], aligned[hclust_k], args.sort_col, args.order_file,
        hc, order_mode, group_order, explicit_cap, language=language,
    )
    order = arranged["order"]
    spans = arranged["spans"]
    dendro_spec = None
    if dendrogram_mode == "top" and arranged["layers"]:
        dendro_spec = {"layers": arranged["layers"]}
    rank = {name: i for i, name in enumerate(blocks)}
    group_color, col_color = parse_colors(args.color, args.color_file, language=language)
    owners = {}
    hexes = {}
    # ks is ascending. A locked column keeps the colour from the lowest K
    # that included it. --color is applied inside assign_colors first.
    locked = []
    for k in ks:
        owners[k] = column_owners(aligned[k], iids, groups, rank)
        lock_from = locked if color_lock == "on" else None
        hexes[k] = assign_colors(
            k, owners[k], group_color, col_color,
            language=language, lock_from=lock_from, palette=palette_name,
        )
        if color_lock == "on" and len(locked) < k:
            locked.extend(hexes[k][len(locked):])
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
    linkage_paths = []
    for _name, _z in arranged["matrices"]:
        _path = os.path.join(args.outdir, _name)
        write_linkage_tsv(_path, _z)
        linkage_paths.append(_path)
        print(_path)
    if arranged["index_groups"] is not None:
        _path = os.path.join(args.outdir, "linkage_index.tsv")
        write_linkage_index(_path, arranged["index_groups"])
        linkage_paths.append(_path)
        print(_path)
    grey_path = None
    if len(rows) == 1:
        out = os.path.join(args.outdir, "bar_K%d.png" % rows[0]["k"])
        render(out, rows, spans, args.width, bar_h, args.title, language=language, dendrogram=dendro_spec)
        print(out)
        grey_src = out
    else:
        for row in rows:
            one = os.path.join(args.outdir, "bar_K%d.png" % row["k"])
            render(one, [row], spans, args.width, max(bar_h, 180), args.title, language=language, dendrogram=dendro_spec)
        panel = os.path.join(args.outdir, "panel.png")
        render(panel, rows, spans, args.width, bar_h, args.title, language=language, dendrogram=dendro_spec)
        print(panel)
        grey_src = panel
    if greyscale:
        grey_path = os.path.join(args.outdir, "panel_grey.png")
        write_greyscale_png(grey_path, grey_src)
        print(grey_path)
    write_tables(args.outdir, iids, groups, order, spans, perm, owners, hexes, meta, aligned)
    groups_auto_tsv = None
    if auto_rows is not None:
        groups_auto_tsv = os.path.join(args.outdir, "groups_auto.tsv")
        write_groups_auto_tsv(groups_auto_tsv, auto_rows)
        groups_auto_summary = os.path.join(args.outdir, "groups_auto_summary.txt")
        write_groups_auto_summary(
            groups_auto_summary,
            auto_rows,
            auto_q,
            known_groups=groups if getattr(args, "groups", None) else None,
            rest_name=args.rest_name,
            details=auto_details,
        )
        print(groups_auto_tsv)
        print(groups_auto_summary)
    report_rows = None
    if args.align_report and meta:
        report_rows = write_align_report(args.outdir, aligned, meta, groups, args.align_method, perm, args.align_report_low)
        if table_rows is not None:
            append_low_confidence_rows(
                os.path.join(args.outdir, "align_report.txt"),
                table_rows,
                args.align_method,
                language=language,
            )
    elif table_rows is not None:
        if args.align_report:
            print(_msg("lowconf_no_report", language), file=sys.stderr)
        else:
            print(_msg("lowconf_unused", language), file=sys.stderr)
    flow_tsv = None
    if flow_mode == "sankey":
        edges = cluster_flow(
            aligned,
            meta,
            args.align_method,
            flow_weight,
            jaccard_set=getattr(args, "jaccard_set", "dominant"),
            jaccard_cut=getattr(args, "jaccard_cut", 0.5),
            report_rows=report_rows,
            language=language,
        )
        flow_tsv = os.path.join(args.outdir, "cluster_flow.tsv")
        write_cluster_flow_tsv(flow_tsv, edges)
        flow_png = os.path.join(args.outdir, "cluster_flow.png")
        write_cluster_flow_plot(flow_png, aligned, edges, hexes)
        print(flow_png)
    if getattr(args, "align_compare", False) and meta:
        write_align_compare(
            args.outdir, q_by_k, aligned, meta, perm, args.align_method,
            args.jaccard_set, args.jaccard_cut,
        )
    support_path = None
    support_rows = []
    # None leaves the bootstrap loop unchanged. A list receives its index vectors.
    boot_indices = [] if parent_ci else None
    if n_boot > 0 and meta:
        support_rows = bootstrap_support(
            q_by_k,
            args.align_method,
            n_boot,
            boot_seed,
            groups=groups,
            anchor=args.anchor_group.strip(),
            align_mode=args.align_mode,
            align_groups=align_groups,
            qmax=args.qmax,
            jaccard_set=args.jaccard_set,
            jaccard_cut=args.jaccard_cut,
            language=language,
            indices_out=boot_indices,
        )
    if n_perm > 0 and meta:
        if not support_rows:
            support_rows = _na_support_rows(perm, meta, args.align_method)
        _attach_permutation(
            support_rows, aligned, q_by_k, meta, args.align_method,
            n_perm, perm_seed, perm_null,
            groups=groups,
            align_mode=args.align_mode,
            align_groups=align_groups,
            qmax=args.qmax,
            jaccard_set=args.jaccard_set,
            jaccard_cut=args.jaccard_cut,
            language=language,
        )
    if support_rows:
        support_path = os.path.join(args.outdir, "match_support.tsv")
        write_match_support(support_path, support_rows)
    parent_path = None
    if (parent_ci or parent_test) and meta:
        parent_rows = parent_interval_rows(
            aligned,
            meta,
            boot_indices,
            parent_alpha,
            n_boot,
            n_perm,
            perm_seed,
            want_ci=parent_ci,
            want_test=parent_test,
            language=language,
        )
        parent_path = os.path.join(args.outdir, "parent_share_ci.tsv")
        write_parent_share_ci(parent_path, parent_rows)
    if log_paths is not None:
        write_cv_loglik_tsv(os.path.join(args.outdir, "cv_loglik.tsv"), log_rows)
        write_cv_loglik_plot(os.path.join(args.outdir, "cv_loglik.png"), log_rows)
        if select_k:
            # The bar K list above is the Q files. This report does not drop a K.
            select_table = select_k_table(log_rows, plateau_fraction=plateau_fraction)
            write_select_k_tsv(os.path.join(args.outdir, "select_k.tsv"), select_table)
            write_select_k_txt(
                os.path.join(args.outdir, "select_k.txt"),
                select_table,
                plateau_fraction=plateau_fraction,
            )
            write_select_k_plot(os.path.join(args.outdir, "select_k.png"), select_table)
    replicate_paths = write_replicate_outputs(args.outdir, replicate_reports)
    with open(os.path.join(args.outdir, "args.txt"), "w") as f:
        f.write(" ".join(sys.argv if argv is None else ["qbar"] + list(argv)) + "\n")
        for k in ks:
            for path in src_paths[k]:
                f.write("K%d\t%s\n" % (k, path))
    run_json = None
    if args.provenance:
        extra_paths = None
        if log_paths is not None:
            extra_paths = list(log_paths)
            if logs_map:
                extra_paths.append(logs_map)
        payload = _provenance_payload(args, argv, files, started, extra_paths)
        plat = payload.pop("platform")
        payload["finished"] = datetime.datetime.now().astimezone().isoformat()
        payload["platform"] = plat
        run_json = os.path.join(args.outdir, "run.json")
        write_run_json(run_json, payload)
    print("order\t%s" % os.path.join(args.outdir, "order.tsv"))
    paths = []
    if len(rows) == 1:
        _bar = os.path.join(args.outdir, "bar_K%d.png" % rows[0]["k"])
        paths.append(_bar)
        paths.append(os.path.splitext(_bar)[0] + ".pdf")
    else:
        for _row in rows:
            _bar = os.path.join(args.outdir, "bar_K%d.png" % _row["k"])
            paths.append(_bar)
            paths.append(os.path.splitext(_bar)[0] + ".pdf")
        _panel = os.path.join(args.outdir, "panel.png")
        paths.append(_panel)
        paths.append(os.path.splitext(_panel)[0] + ".pdf")
    if grey_path is not None:
        paths.append(grey_path)
    paths.append(os.path.join(args.outdir, "order.tsv"))
    paths.append(os.path.join(args.outdir, "blocks.tsv"))
    paths.extend(linkage_paths)
    for _k in sorted(perm):
        paths.append(os.path.join(args.outdir, "perm_K%d.tsv" % _k))
    if meta:
        paths.append(os.path.join(args.outdir, "align.tsv"))
    if args.align_report and meta:
        paths.append(os.path.join(args.outdir, "align_report.tsv"))
        paths.append(os.path.join(args.outdir, "align_report.txt"))
    if getattr(args, "align_compare", False) and meta:
        paths.append(os.path.join(args.outdir, "align_compare.tsv"))
        paths.append(os.path.join(args.outdir, "align_compare.txt"))
    if support_path is not None:
        paths.append(support_path)
    if parent_path is not None:
        paths.append(parent_path)
    if flow_tsv is not None:
        paths.append(flow_tsv)
        paths.append(os.path.join(args.outdir, "cluster_flow.png"))
        paths.append(os.path.join(args.outdir, "cluster_flow.pdf"))
    if groups_auto_tsv is not None:
        paths.append(groups_auto_tsv)
        paths.append(os.path.join(args.outdir, "groups_auto_summary.txt"))
    if log_paths is not None:
        paths.append(os.path.join(args.outdir, "cv_loglik.tsv"))
        paths.append(os.path.join(args.outdir, "cv_loglik.png"))
        paths.append(os.path.join(args.outdir, "cv_loglik.pdf"))
        if select_k:
            paths.append(os.path.join(args.outdir, "select_k.tsv"))
            paths.append(os.path.join(args.outdir, "select_k.txt"))
            paths.append(os.path.join(args.outdir, "select_k.png"))
            paths.append(os.path.join(args.outdir, "select_k.pdf"))
    paths.extend(replicate_paths)
    paths.append(os.path.join(args.outdir, "args.txt"))
    if run_json is not None:
        paths.append(run_json)
    return RunResult(
        aligned=aligned,
        permutations=perm,
        order=order,
        spans=spans,
        colours=hexes,
        paths=paths,
    )
