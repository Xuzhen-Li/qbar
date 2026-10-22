"""Programmatic entry point.

``run`` accepts the namespace from ``build_parser``. K is the column
count. Permutations are 0-based in the returned arrays and 1-based in
the TSV files.
"""
from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass

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
    """
    # Imported on call so this module can be imported without the drawing code.
    from .plot_static import ancestry_image, assign_colors, render

    check_hclust_opts(args.hclust_dist, args.hclust_linkage)
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
        {"dist": args.hclust_dist, "link": args.hclust_linkage, "olo": args.hclust_olo, "pre": args.hclust_pre},
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
    paths.append(os.path.join(args.outdir, "args.txt"))
    return RunResult(
        aligned=aligned,
        permutations=perm,
        order=order,
        spans=spans,
        colours=hexes,
        paths=paths,
    )
