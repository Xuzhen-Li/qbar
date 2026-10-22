#!/usr/bin/env python3
"""Plot ADMIXTURE Q files: sort people, align columns across K, write a bar.

One command. No R, no CLUMPP. Same-K replicate merging is not done here
(that is CLUMPP: Jakobsson & Rosenberg 2007 Bioinformatics 23:1801,
DOI 10.1093/bioinformatics/btm233).

Cross-K column matching runs from K to K+1. The default --align-method
is greedy: each old column takes the unused new column with the highest
Pearson correlation. Other --align-method choices are hungarian, pong,
and jaccard. --align-report writes align_report.tsv and align_report.txt.
Label switching itself is described by Alexander, Novembre & Lange 2009
Genome Res 19:1655, DOI 10.1101/gr.094052.109.

Within-group hclust default is average linkage on correlation distance
(1 - Pearson): scipy.cluster.hierarchy.linkage(method="average",
metric="correlation"). --hclust-dist also accepts euclidean and
braycurtis. --hclust-linkage also accepts ward and complete; ward needs
--hclust-dist euclidean. --hclust-pre accepts dominant (default none).
--hclust-olo is off unless set.
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

from .align import (
    ALIGN_METHODS,
    JACCARD_SETS,
    align_qs,
    anchor_perm,
    col_pearson,
    core_mask,
    jaccard_matrix,
    match_next,
    match_next_hungarian,
    match_next_jaccard,
    match_next_pong,
    member_sets,
    pearson_matrix,
    pong_sim,
)
from .api import (
    RunResult,
    column_owners,
    legend_lines,
    parse_within,
    run,
)
from .io import (
    check_shapes,
    collect_q,
    k_of,
    load_groups,
    load_ids,
    load_q_set,
    norm_hex,
    order_from_file,
    parse_colors,
    read_q,
)
from .order import (
    HCLUST_DIST,
    HCLUST_LINK,
    HCLUST_PRE,
    WITHIN,
    build_order,
    check_hclust_opts,
    hclust_block_order,
    hclust_order,
    sort_block,
    spans_of,
)
from .report import (
    REPORT_COLS,
    REPORT_LOW,
    align_report_rows,
    column_label,
    dominant_groups,
    parent_shares,
    split_parent_of,
    top_groups,
    top_mean,
    write_align_report,
    write_tables,
)

# csv, glob, os, OrderedDict, and np stay bound here so `import qbar` still
# exposes the names the single-file module used to bind.



class HelpFormatter(argparse.RawDescriptionHelpFormatter, argparse.ArgumentDefaultsHelpFormatter):
    pass


def build_parser():
    p = argparse.ArgumentParser(
        prog="qbar",
        description="读 ADMIXTURE 的 Q，按指定规则排人，跨 K 对齐列，写出结构条形图。",
        formatter_class=HelpFormatter,
        epilog="排序：--order-file 用你给的名单；否则按 --blocks 的组序分块，组内用 --within。\n"
        "组内 iid=名字，q=该组占比最高的那一列从高到低，hclust=平均连锁、距离 1−Pearson，input=Q 里的原顺序。\n"
        "多个 K 默认做 Pearson 贪心对齐，新列放在最上面。--no-align 保持每个 Q 自己的列顺序；若同时给了 --anchor-group，每个 K 仍把该组最纯的人的主列放到 C1。",
    )
    p.add_argument("--q", nargs="+", required=True, help="一个或多个 .Q 或 .q，或带引号的通配符，或一个目录（读取其中的 .Q 和 .q）。只读空白分隔的数字 .Q 或 .q")
    p.add_argument("--q-format", choices=("admixture", "meanq", "qopt"), default="admixture",
                   help="指定读取的矩阵排版")
    p.add_argument("--fam", help="PLINK .fam，IID 在第 2 列，行序与 Q 相同")
    p.add_argument("--ids", help="一行一个 IID，行序与 Q 相同。与 --fam 二选一。多出来的字段只保留第一个，并在 stderr 警告")
    p.add_argument("--ind", help="EIGENSTRAT 的 .ind，三列，样本号在第 1 列")
    p.add_argument("--groups", help="分组表，tsv 或 csv，要有表头")
    p.add_argument("--id-col", default="analysis_IID")
    p.add_argument("--group-col", default="Dong_Grp")
    p.add_argument("--blocks", default="", help="组的从左到右顺序，逗号分隔。组名不能含逗号，否则会被拆开。没写到的组按名字接在后面")
    p.add_argument("--rest-name", default="NA", help="分组为空的人用这个名字。默认 NA")
    p.add_argument("--within", default="iid", choices=WITHIN, help="每一组内部怎么排。默认 iid")
    p.add_argument("--within-group", action="append", default=[], help="单独改某一组，例如 NA=hclust。可重复")
    p.add_argument("--order-file", help="一行一个 IID，这就是从左到右的顺序。给了它就不再用 --blocks")
    p.add_argument("--sort-k", type=int, help="按组分排序时用哪个 K。默认最大的 K")
    p.add_argument("--sort-col", type=int, help="所有按 q 排序的组都用这一列（从 1 数）。不给就每组用自己占比最高的列")
    p.add_argument("--hclust-k", type=int, help="hclust 用哪个 K。默认与 --sort-k 相同")
    p.add_argument("--hclust-dist", choices=HCLUST_DIST, default="correlation",
                   help="hclust 距离。默认 correlation（1−Pearson）")
    p.add_argument("--hclust-linkage", choices=HCLUST_LINK, default="average",
                   help="hclust 连锁法。默认 average。ward 只能配 euclidean")
    p.add_argument("--hclust-pre", choices=HCLUST_PRE, default="none",
                   help="dominant=组内先按每人最高的列分小块（C1、C2…顺序），块内再 hclust。默认 none")
    p.add_argument("--hclust-olo", action="store_true",
                   help="叶序用 scipy optimal_leaf_ordering")
    p.add_argument("--align", dest="align", action="store_true")
    p.add_argument("--no-align", dest="align", action="store_false")
    p.set_defaults(align=None)
    p.add_argument("--align-mode", choices=("all", "core"), default="all",
                   help="all=掩码内所有人参与对齐，greedy、hungarian、pong、jaccard 用同一批人。Pearson 只用于 greedy 和 hungarian。core=只留相邻两个 K 的 qmax 都严格大于 --qmax 的人；某一组没有人超过时，留下该组在较低 K 上最纯的一个人")
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
    p.add_argument("--anchor-group", default="", help="对齐时只改最低 K，把这个组最纯的人的主列放到 C1。--no-align 或只有一个 K 时，每个 K 都这样做。")
    p.add_argument("--color", action="append", default=[], help="组名=#rrggbb 或 C3=#rrggbb，在第一个等号处分开。组名不能含等号。可重复")
    p.add_argument("--color-file", help="两列：名字 #rrggbb")
    p.add_argument("--title", default="")
    p.add_argument("--width", type=int, default=2200, help="条形图宽度，像素")
    p.add_argument("--bar-height", type=int, default=0, help="每一行条的高度。单个 K 默认 220，多个 K 默认 120")
    p.add_argument("--outdir", required=True)
    p.add_argument("--provenance", action="store_true",
                   help="另写 run.json，记下版本、选项、输入哈希和依赖版本")
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    run(args, argv)
    return 0


if __name__ == "__main__":
    sys.exit(main())
