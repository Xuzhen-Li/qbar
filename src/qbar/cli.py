#!/usr/bin/env python3
"""Plot ADMIXTURE Q files: sort people, align columns across K, write a bar.

One command. No R, no CLUMPP. Same-K replicates are grouped into modes
only when --replicates is set, using qbar's own connected components.
That is not the CLUMPP alignment of Jakobsson & Rosenberg 2007
Bioinformatics 23:1801, DOI 10.1093/bioinformatics/btm233.

Cross-K column matching runs from K to K+1. The default --align-method
is greedy: each old column takes the unused new column with the highest
Pearson correlation. Other --align-method choices are hungarian, pong,
jaccard, clumpp-full, clumpp-greedy, clumpp-largek, and clumppling-ilp. --align-report writes align_report.tsv and
align_report.txt. --low-confidence-table copies precision and recall rows for the
active method onto the end of align_report.txt when --align-report is also set.
It does not change the low-confidence cut.
Label switching itself is described by Alexander, Novembre & Lange 2009
Genome Res 19:1655, DOI 10.1101/gr.094052.109.

Within-group hclust default is average linkage on correlation distance
(1 - Pearson): scipy.cluster.hierarchy.linkage(method="average",
metric="correlation"). --hclust-dist also accepts euclidean and
braycurtis. --hclust-linkage also accepts ward and complete; ward needs
--hclust-dist euclidean. --hclust-pre accepts dominant (default none).
--hclust-olo is off unless set.
--order-mode within (the default) orders inside groups. global-hclust
clusters every row as one tree. group-hclust keeps each group together
and can order the groups by the mean Q row. --dendrogram top draws that
tree above the bars. The default none draws none. --hclust-max-bytes
limits the distance vector. When it is omitted, the new modes use
4294967296 bytes for the all-rows vector or the between-group vector.
--auto-groups hclust uses that same cap on every row. --auto-groups none
(the default) writes no groups file. major names a row C1, C2, ... from
its highest column, lowest index on a tie. threshold names a row admixed
only when the maximum is below --admix-cut. hclust and kmeans name groups
G1, G2, ... in order of first appearance. Those two accept --pca with
--pca-n, a PLINK 1.9 eigenvec with no header. Auto groups do not replace
--groups.
--palette chooses bar colours. The default is science. classic is the
previous 20 colours. --color-lock on keeps each aligned column's colour
from the lowest K unless --color sets that column. The default is off.
--greyscale-preview writes panel_grey.png and is off by default.
--vector off (the default) keeps the PNG and the raster PDF. pdf writes
bar_K*.pdf and panel.pdf as vectors. svg also writes SVG and keeps the
PDF raster. both writes vector PDFs and SVGs. PNG stays raster. A vector
file with more than 200000 bar rectangles is refused and no output file
is written.
--html writes panel.html and is off by default. The file embeds the
sample rows and draws the bars on a canvas. Hover text shows the sample.
It does not load a network file.
--editor writes editor.html and state.json and is off by default. The
page reuses that canvas. It can move a sample within its group, reorder
groups, swap two columns at one K, rename a column, and set a column
colour. --state replays state.json after alignment. It cannot be combined
with --order-file, --color, or --color-file.
--config reads a YAML file of settings and is omitted by default.
Precedence is the command line, then the file, then the defaults. A flag
on the command line wins even when its value equals the default. Keys are
argparse dest names. Without PyYAML, --config exits and names
pip install "qbar[config]".
--sites is omitted by default. When set, map_pies.png and map_pies.tsv
are written for the aligned Q at --sort-k, or at the largest K when
--sort-k is omitted. Mean Q is the mean of every sample in that group.
The alignment mask does not drop those samples. --basemap-image and
--basemap-bbox must be given together. A world file is not read. Nothing
is downloaded. --vector does not write a map PDF or SVG.
--export none (the default) writes no export directory. clumpp writes
K<k>.indfile, K<k>.popq, names.txt, and ids.tsv under export/clumpp.
Indfile column 2 is the same running index as column 1. ids.tsv maps
that index to the iid. pong writes K<k>.Q, filemap.txt, and ind2pop.txt
under export/pong. A comma-separated list can name both. Rows follow
the bar. Values are not rescaled.
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
    match_next_clumppling_ilp,
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
from .exports import export_clumpp, export_pong
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
    DENDROGRAMS,
    GROUP_ORDERS,
    HCLUST_DIST,
    HCLUST_LINK,
    HCLUST_PRE,
    ORDER_MODES,
    WITHIN,
    DEFAULT_HCLUST_MAX_BYTES,
    build_order,
    cap_for_tree,
    check_hclust_bytes,
    check_hclust_opts,
    group_hclust_order,
    hclust_block_order,
    hclust_order,
    linkage_matrix,
    pdist_nbytes,
    resolve_hclust_max_bytes,
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


def _attach_negative_bbox(args):
    """Keep a negative --basemap-bbox value attached to the flag.

    ``-10,-10,10,10`` does not match argparse's negative-number pattern,
    because of the commas, so it would be read as another flag. Writing
    it as ``--basemap-bbox=-10,-10,10,10`` keeps the four numbers together.
    """
    items = list(args)
    out = []
    index = 0
    while index < len(items):
        item = items[index]
        if item == "--basemap-bbox" and index + 1 < len(items):
            nxt = items[index + 1]
            if nxt.startswith("-") and not nxt.startswith("--"):
                out.append(item + "=" + nxt)
                index += 2
                continue
        out.append(item)
        index += 1
    return out


class _Parser(argparse.ArgumentParser):
    def parse_known_args(self, args=None, namespace=None):
        if args is None:
            args = sys.argv[1:]
        return super().parse_known_args(_attach_negative_bbox(args), namespace)


def build_parser(language="en"):
    def say(key):
        return _msg(key, language)

    p = _Parser(
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
    p.add_argument("--sites", default=None, help=say("help_sites"))
    p.add_argument("--basemap-image", default=None, help=say("help_basemap_image"))
    p.add_argument("--basemap-bbox", default=None, help=say("help_basemap_bbox"))
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
    p.add_argument("--order-mode", choices=ORDER_MODES, default="within",
                   help=say("help_order_mode"))
    p.add_argument("--group-order", choices=GROUP_ORDERS, default="input",
                   help=say("help_group_order"))
    p.add_argument("--dendrogram", choices=DENDROGRAMS, default="none",
                   help=say("help_dendrogram"))
    p.add_argument("--hclust-max-bytes", type=int, default=None,
                   help=say("help_hclust_max_bytes"))
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
    p.add_argument("--align-compare", action="store_true",
                   help=say("help_align_compare"))
    p.add_argument("--align-report-low", type=float,
                   help=say("help_align_report_low"))
    p.add_argument("--low-confidence-table", default=None,
                   help=say("help_low_confidence_table"))
    p.add_argument("--align-groups", default="", help=say("help_align_groups"))
    p.add_argument("--qmax", type=float, default=0.75, help=say("help_qmax"))
    p.add_argument("--anchor-group", default="", help=say("help_anchor_group"))
    p.add_argument("--color", action="append", default=[], help=say("help_color"))
    p.add_argument("--color-file", help=say("help_color_file"))
    p.add_argument("--palette", choices=("science", "classic", "tab10", "set1", "dark2", "paired"),
                   default="science", help=say("help_palette"))
    p.add_argument("--color-lock", choices=("off", "on"), default="off",
                   help=say("help_color_lock"))
    p.add_argument("--greyscale-preview", action="store_true",
                   help=say("help_greyscale_preview"))
    p.add_argument("--vector", choices=("off", "pdf", "svg", "both"), default="off",
                   help=say("help_vector"))
    p.add_argument("--html", action="store_true", help=say("help_html"))
    p.add_argument("--editor", action="store_true", help=say("help_editor"))
    p.add_argument("--state", default=None, help=say("help_state"))
    p.add_argument("--config", default=None, help=say("help_config"))
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
    p.add_argument("--bootstrap", type=int, default=0, help=say("help_bootstrap"))
    p.add_argument("--bootstrap-seed", type=int, default=0,
                   help=say("help_bootstrap_seed"))
    p.add_argument("--perm", type=int, default=0, help=say("help_perm"))
    p.add_argument("--perm-seed", type=int, default=0, help=say("help_perm_seed"))
    p.add_argument("--perm-null", choices=("rows", "column"), default=None,
                   help=say("help_perm_null"))
    p.add_argument("--parent-ci", action="store_true",
                   help=say("help_parent_ci"))
    p.add_argument("--parent-alpha", type=float, default=0.05,
                   help=say("help_parent_alpha"))
    p.add_argument("--parent-test", action="store_true",
                   help=say("help_parent_test"))
    p.add_argument("--cluster-flow", choices=("none", "sankey"), default="none",
                   help=say("help_cluster_flow"))
    p.add_argument("--flow-weight", choices=("share", "jaccard"), default="share",
                   help=say("help_flow_weight"))
    p.add_argument("--auto-groups", choices=("none", "major", "threshold", "hclust", "kmeans"),
                   default="none", help=say("help_auto_groups"))
    p.add_argument("--auto-k", type=int, default=None, help=say("help_auto_k"))
    p.add_argument("--admix-cut", type=float, default=0.5, help=say("help_admix_cut"))
    p.add_argument("--auto-g", type=int, default=None, help=say("help_auto_g"))
    p.add_argument("--auto-seed", type=int, default=0, help=say("help_auto_seed"))
    p.add_argument("--pca", default=None, help=say("help_pca"))
    p.add_argument("--pca-n", type=int, default=None, help=say("help_pca_n"))
    p.add_argument("--export", default="none", help=say("help_export"))
    return p


def _consumes_value(action):
    """True when this option takes the next argv token as its value."""
    if isinstance(action, (
        argparse._StoreTrueAction,
        argparse._StoreFalseAction,
        argparse._HelpAction,
        argparse._AppendConstAction,
        argparse._CountAction,
        argparse._VersionAction,
    )):
        return False
    if action.nargs == 0:
        return False
    return bool(action.option_strings)


def _requests_help(argv, language):
    """True when ``-h`` or ``--help`` is an option, not a consumed value."""
    if not any(item in ("-h", "--help") for item in argv):
        return False
    consumes = set()
    for action in build_parser(language)._actions:
        if not _consumes_value(action):
            continue
        for opt in action.option_strings:
            consumes.add(opt)
    index = 0
    while index < len(argv):
        item = argv[index]
        if item == "--":
            return False
        if item in ("-h", "--help"):
            return True
        if item in consumes:
            index += 2
            continue
        index += 1
    return False


def _explicit_namespace(argv, language):
    """Parse ``argv`` with defaults suppressed.

    A dest that the user did not pass is absent. Comparing with the
    ordinary default would miss a flag the user set to that default.
    """
    parser = build_parser(language)
    parser._defaults.clear()
    for action in parser._actions:
        if isinstance(action, argparse._HelpAction):
            continue
        action.required = False
        action.default = argparse.SUPPRESS
    return parser.parse_args(argv)


def _note_config_replaced_by_state(args, coerced, explicit, language):
    """Ignore config colour and order files when ``--state`` replaces them.

    Command-line ``--color``, ``--color-file``, and ``--order-file`` stay
    on the namespace, so the existing conflict errors still run. Each
    ignored key is recorded as the config value and ``used: state``.
    One stderr line names every ignored key.
    """
    if not getattr(args, "state", None):
        return {}
    recorded = {}
    names = []
    for dest in ("color", "color_file", "order_file"):
        if dest not in coerced or dest in explicit:
            continue
        value = coerced[dest]
        if not value:
            continue
        if dest in ("color_file", "order_file"):
            value = os.path.basename(value)
        recorded[dest] = {"config": value, "used": "state"}
        if dest == "color":
            args.color = []
        else:
            setattr(args, dest, None)
        names.append(dest)
    if names:
        print(
            _msg("config_replaced_by_state", language, option=", ".join(names)),
            file=sys.stderr,
        )
    return recorded


def _state_align_override(args, coerced, explicit, language):
    """Record a state override, and maybe use the state's align method.

    Order and colours are replaced whenever ``--state`` is set. The align
    method changes only when the config file set it, the command line did
    not, and the state names another known method. A command-line
    ``--align-method`` still has to match the state inside ``apply_state``.
    """
    if not getattr(args, "state", None):
        return None
    override = {"colours": "state", "order": "state"}
    if "align_method" not in coerced or "align_method" in explicit:
        return override
    from .state import load_state
    state = load_state(args.state, language=language)
    method = state.get("align_method")
    if method in ALIGN_METHODS and method != args.align_method:
        override["align_method"] = {
            "config": coerced["align_method"],
            "state": method,
        }
        args.align_method = method
    return override


def main(argv=None):
    language = _language_from_argv(argv)
    passed = list(sys.argv[1:] if argv is None else argv)
    if _requests_help(passed, language):
        build_parser(language).parse_args(argv)
        return 0
    seen = _explicit_namespace(passed, language)
    explicit = {key for key in vars(seen) if key != "help"}
    if "config" not in explicit:
        args = build_parser(language).parse_args(argv)
        run(args, argv)
        return 0
    from .config import apply_file_defaults, load_config, resolved_text, write_resolved_text
    data = load_config(seen.config, language=language)
    parser = build_parser(language)
    coerced = apply_file_defaults(parser, data, explicit, language=language)
    args = parser.parse_args(argv)
    override = _state_align_override(args, coerced, explicit, language)
    replaced = _note_config_replaced_by_state(args, coerced, explicit, language)
    if replaced:
        override = dict(override or {})
        override.update(replaced)
    text = resolved_text(
        args, build_parser(language), seen.config, explicit, coerced, override,
        language,
    )
    run(args, argv)
    write_resolved_text(args.outdir, text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
