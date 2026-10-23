#!/usr/bin/env python3
"""Plot ADMIXTURE Q files: sort people, align columns across K, write a bar.

One command. No R, no CLUMPP. Same-K replicates are grouped into modes
only when --replicates is set, using qbar's own connected components.
That is not the CLUMPP alignment of Jakobsson & Rosenberg 2007
Bioinformatics 23:1801, DOI 10.1093/bioinformatics/btm233.

Cross-K column matching runs from K to K+1. The default --align-method
is greedy: each old column takes the unused new column with the highest
Pearson correlation. Other --align-method choices are hungarian, pong,
jaccard, clumpp-full, clumpp-greedy, and clumpp-largek. --align-report writes align_report.tsv and
align_report.txt.
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
    match_next_clumpp_full,
    match_next_clumpp_greedy,
    match_next_clumpp_largek,
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
from .messages import text as _msg
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


def _language_from_argv(argv):
    """Return en or zh from --language before argparse formats help."""
    if argv is None:
        argv = sys.argv[1:]
    language = "en"
    i = 0
    while i < len(argv):
        item = argv[i]
        if item == "--":
            break
        if item == "--language":
            if i + 1 < len(argv) and argv[i + 1] in ("en", "zh"):
                language = argv[i + 1]
                i += 2
                continue
            i += 1
            continue
        if item.startswith("--language="):
            value = item.split("=", 1)[1]
            if value in ("en", "zh"):
                language = value
        i += 1
    return language


def build_parser(language="en"):
    def say(key):
        return _msg(key, language)

    p = argparse.ArgumentParser(
        prog="qbar",
        description=say("description"),
        formatter_class=HelpFormatter,
        epilog=say("epilog"),
    )
    p.add_argument("--q", nargs="+", required=True, help=say("help_q"))
    p.add_argument("--q-format", choices=("admixture", "meanq", "qopt"), default="admixture",
                   help=say("help_q_format"))
    p.add_argument("--fam", help=say("help_fam"))
    p.add_argument("--ids", help=say("help_ids"))
    p.add_argument("--ind", help=say("help_ind"))
    p.add_argument("--groups", help=say("help_groups"))
    p.add_argument("--id-col", default="analysis_IID")
    p.add_argument("--group-col", default="Dong_Grp")
    p.add_argument("--blocks", default="", help=say("help_blocks"))
    p.add_argument("--rest-name", default="NA", help=say("help_rest_name"))
    p.add_argument("--within", default="iid", choices=WITHIN, help=say("help_within"))
    p.add_argument("--within-group", action="append", default=[], help=say("help_within_group"))
    p.add_argument("--order-file", help=say("help_order_file"))
    p.add_argument("--sort-k", type=int, help=say("help_sort_k"))
    p.add_argument("--sort-col", type=int, help=say("help_sort_col"))
    p.add_argument("--hclust-k", type=int, help=say("help_hclust_k"))
    p.add_argument("--hclust-dist", choices=HCLUST_DIST, default="correlation",
                   help=say("help_hclust_dist"))
    p.add_argument("--hclust-linkage", choices=HCLUST_LINK, default="average",
                   help=say("help_hclust_linkage"))
    p.add_argument("--hclust-pre", choices=HCLUST_PRE, default="none",
                   help=say("help_hclust_pre"))
    p.add_argument("--hclust-olo", action="store_true",
                   help=say("help_hclust_olo"))
    p.add_argument("--align", dest="align", action="store_true")
    p.add_argument("--no-align", dest="align", action="store_false")
    p.set_defaults(align=None)
    p.add_argument("--align-mode", choices=("all", "core"), default="all",
                   help=say("help_align_mode"))
    p.add_argument("--align-method", choices=ALIGN_METHODS, default="greedy",
                   help=say("help_align_method"))
    p.add_argument("--jaccard-set", choices=JACCARD_SETS, default="dominant",
                   help=say("help_jaccard_set"))
    p.add_argument("--jaccard-cut", type=float, default=0.5, help=say("help_jaccard_cut"))
    p.add_argument("--align-report", action="store_true",
                   help=say("help_align_report"))
    p.add_argument("--align-report-low", type=float,
                   help=say("help_align_report_low"))
    p.add_argument("--align-groups", default="", help=say("help_align_groups"))
    p.add_argument("--qmax", type=float, default=0.75, help=say("help_qmax"))
    p.add_argument("--anchor-group", default="", help=say("help_anchor_group"))
    p.add_argument("--color", action="append", default=[], help=say("help_color"))
    p.add_argument("--color-file", help=say("help_color_file"))
    p.add_argument("--title", default="")
    p.add_argument("--width", type=int, default=2200, help=say("help_width"))
    p.add_argument("--bar-height", type=int, default=0, help=say("help_bar_height"))
    p.add_argument("--outdir", required=True)
    p.add_argument("--provenance", action="store_true",
                   help=say("help_provenance"))
    p.add_argument("--language", choices=("en", "zh"), default="en",
                   help=say("help_language"))
    p.add_argument("--logs", nargs="+", help=say("help_logs"))
    p.add_argument("--logs-map", help=say("help_logs_map"))
    p.add_argument("--select-k", action="store_true", help=say("help_select_k"))
    p.add_argument("--plateau-fraction", type=float, default=0.05,
                   help=say("help_plateau_fraction"))
    p.add_argument("--replicates", action="store_true", help=say("help_replicates"))
    p.add_argument("--mode-sim-cut", type=float, default=None,
                   help=say("help_mode_sim_cut"))
    return p


def main(argv=None):
    args = build_parser(language=_language_from_argv(argv)).parse_args(argv)
    run(args, argv)
    return 0


if __name__ == "__main__":
    sys.exit(main())
