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
from .io import (
    check_shapes,
    collect_q,
    load_groups,
    load_ids,
    load_q_set,
    parse_colors,
)
from .logs import (
    check_logs_map,
    collect_logs,
    parse_admixture_log,
    write_cv_loglik_tsv,
)
from .messages import text as _msg
from .selectk import select_k_table, write_select_k_tsv, write_select_k_txt
from .order import WITHIN, build_order, check_hclust_opts
from .report import column_label, write_align_report, write_tables


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
    for path in (args.fam, args.ids, args.ind, args.groups, args.order_file, args.color_file):
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
    """
    if args.provenance:
        started = datetime.datetime.now().astimezone().isoformat()
    else:
        started = None
    # Imported on call so this module can be imported without the drawing code.
    from .plot_static import (
        ancestry_image, assign_colors, render, write_cv_loglik_plot, write_select_k_plot,
    )

    language = args.language
    check_hclust_opts(args.hclust_dist, args.hclust_linkage, language=language)
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
    if logs:
        log_paths = collect_logs(logs, language=language)
        if logs_map:
            check_logs_map(logs_map, log_paths, language=language)
        log_rows = []
        for log_path in log_paths:
            log_rows.extend(parse_admixture_log(log_path, language=language))
    files = collect_q(args.q, format=args.q_format, language=language)
    q_by_k, src = load_q_set(files, format=args.q_format, language=language)
    iids = load_ids(args.fam, args.ids, ind=args.ind, language=language)
    check_shapes(q_by_k, len(iids), language=language)
    groups = load_groups(args.groups, iids, args.id_col, args.group_col, args.rest_name, language=language)
    within_group = parse_within(args.within_group, language=language)
    unknown = sorted(set(within_group) - set(groups))
    if unknown:
        print(_msg("within_group_missing", language, names=", ".join(unknown)), file=sys.stderr)
    blocks = [x.strip() for x in args.blocks.split(",") if x.strip()] if args.blocks else []
    align_groups = [x.strip() for x in args.align_groups.split(",") if x.strip()]
    do_align = (len(q_by_k) > 1) if args.align is None else args.align
    aligned, perm, meta = align_qs(
        q_by_k, groups, args.anchor_group.strip(), args.align_mode,
        align_groups, args.qmax, do_align, args.align_method,
        args.jaccard_set, args.jaccard_cut, language=language,
    )
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
    order, spans = build_order(
        iids, groups, blocks, args.within, within_group, args.rest_name,
        aligned[sort_k], aligned[hclust_k], args.sort_col, args.order_file,
        {"dist": args.hclust_dist, "link": args.hclust_linkage, "olo": args.hclust_olo, "pre": args.hclust_pre},
        language=language,
    )
    rank = {name: i for i, name in enumerate(blocks)}
    group_color, col_color = parse_colors(args.color, args.color_file, language=language)
    owners = {}
    hexes = {}
    for k in ks:
        owners[k] = column_owners(aligned[k], iids, groups, rank)
        hexes[k] = assign_colors(k, owners[k], group_color, col_color, language=language)
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
        render(out, rows, spans, args.width, bar_h, args.title, language=language)
        print(out)
    else:
        for row in rows:
            one = os.path.join(args.outdir, "bar_K%d.png" % row["k"])
            render(one, [row], spans, args.width, max(bar_h, 180), args.title, language=language)
        panel = os.path.join(args.outdir, "panel.png")
        render(panel, rows, spans, args.width, bar_h, args.title, language=language)
        print(panel)
    write_tables(args.outdir, iids, groups, order, spans, perm, owners, hexes, meta, aligned)
    if args.align_report and meta:
        write_align_report(args.outdir, aligned, meta, groups, args.align_method, perm, args.align_report_low)
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
    with open(os.path.join(args.outdir, "args.txt"), "w") as f:
        f.write(" ".join(sys.argv if argv is None else ["qbar"] + list(argv)) + "\n")
        for k in ks:
            f.write("K%d\t%s\n" % (k, src[k]))
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
    paths.append(os.path.join(args.outdir, "order.tsv"))
    paths.append(os.path.join(args.outdir, "blocks.tsv"))
    for _k in sorted(perm):
        paths.append(os.path.join(args.outdir, "perm_K%d.tsv" % _k))
    if meta:
        paths.append(os.path.join(args.outdir, "align.tsv"))
    if args.align_report and meta:
        paths.append(os.path.join(args.outdir, "align_report.tsv"))
        paths.append(os.path.join(args.outdir, "align_report.txt"))
    if log_paths is not None:
        paths.append(os.path.join(args.outdir, "cv_loglik.tsv"))
        paths.append(os.path.join(args.outdir, "cv_loglik.png"))
        paths.append(os.path.join(args.outdir, "cv_loglik.pdf"))
        if select_k:
            paths.append(os.path.join(args.outdir, "select_k.tsv"))
            paths.append(os.path.join(args.outdir, "select_k.txt"))
            paths.append(os.path.join(args.outdir, "select_k.png"))
            paths.append(os.path.join(args.outdir, "select_k.pdf"))
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
