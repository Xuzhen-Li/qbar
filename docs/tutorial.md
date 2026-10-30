# Tutorial

This walk-through uses the bundled demo. Each command is run from the repository root. The paths are the same `demo/2448` directory the README uses. An ADMIXTURE Q matrix file is a table that shows how much of each sample's genetic makeup comes from each ancestral group, where K is the number of ancestral groups tested. The README quick start quotes a wildcard that matches every Q file in that directory. The commands below use `demo/2448/ref2448_pruned.2.Q` and `demo/2448/ref2448_pruned.3.Q`, so each step is one K to the next and the tables stay short.

The program in these commands is `qbar`, the command installed from this repository. There are no figures on this page. The output below is text the commands wrote.

## (a) Install and check the version

Do this so the `qbar` command and the import below are the package in this repository. If you skip it, the later commands have nothing to run.

The install text is copied from the README.

qbar needs Python 3, numpy, and Pillow. scipy is needed only for `--within hclust` or `--within-group X=hclust` (and all `--hclust-*` options), and for `--align-method` `hungarian`, `pong` and `jaccard`. Hclust (hierarchical clustering) groups similar samples together automatically, while alignment methods like greedy, hungarian, pong, and jaccard are different mathematical ways to match ancestral group columns from K-1 to K. Default greedy alignment and everything else need only numpy and Pillow, though scipy is already in `requirements.txt`.

```bash
git clone https://github.com/Xuzhen-Li/qbar.git
cd qbar
```

The README Install section then creates a virtual environment, activates it, and runs `python3 -m pip install -r requirements.txt`.

After the first PyPI release, install the package with:

```bash
pip install qbar-plot
```

That command is not available before the first PyPI release. From a checkout of this repository, install the same package with:

```bash
pip install .
```

The installed command is `qbar`. `python3 qbar.py` still runs the program from a checkout.

Check the version so you know which package you imported. If you skip the check, the later commands still run, and you have not printed the version string. The parser has no version option. This print is that string:

```bash
python -c "import qbar; print(qbar.__version__)"
```

```text
0.3.0
```

## (b) The default run

Do this first so you can see the files a run writes before you change alignment, order, or colours. If you skip it, you have no plot and no tables.

The groups file header is `id` and `group`. The command names those columns. Section (d) shows the message when they are left off.

A PLINK `.fam` file is a standard genetics table of sample information, and an IID (individual identifier) is the unique name for one sample. `--q` lists the Q files. `--fam` names that `.fam` file: the IID is in column 2, and the row order matches the Q file. `--groups` names the group table. `--outdir` names the directory the run writes.

```bash
qbar \
  --q demo/2448/ref2448_pruned.2.Q demo/2448/ref2448_pruned.3.Q \
  --fam demo/2448/ref2448_pruned.fam \
  --groups demo/2448/groups.tsv \
  --id-col id \
  --group-col group \
  --outdir out/default
```

The command writes no warning. The terminal prints the panel path and a second line that starts with `order`, then a tab, then the path of `order.tsv`. The directory contains:

```text
align.tsv
args.txt
bar_K2.pdf
bar_K2.png
bar_K3.pdf
bar_K3.png
blocks.tsv
order.tsv
panel.pdf
panel.png
perm_K2.tsv
perm_K3.tsv
```

`bar_K2.png` and `bar_K3.png` are the bar plots for one K each, with a PDF beside each PNG. `panel.png` and `panel.pdf` stack both K values. `order.tsv` is the left-to-right sample order. `blocks.tsv` is the start and end of each group on that order. `args.txt` records the command and the Q path for each K.

`perm_K2.tsv` and `perm_K3.tsv` map each aligned column to the raw column in that K's Q file. `C` is the aligned name (`C1`, `C2`, ...). `raw` is the 1-based column in the Q file. `hex` is the colour used for that aligned column. `owners` is the label written for that column.

```text
C	raw	hex	owners
C1	1	#4470b7	W-Ad+WWE1+WWE2
C2	2	#dc1f26	C-Ad+CG1+CG2+CG3+CG4+CG5+CG6+WEE1+WEE2
```

```text
C	raw	hex	owners
C1	3	#4470b7	W-Ad+WWE1+WWE2
C2	1	#dc1f26	CG1+CG2+WEE1+WEE2
C3	2	#981b1e	C-Ad+CG3+CG4+CG5+CG6
```

`align.tsv` is the score of the match from one K to the next. For this run the header is `K_to`, `n_mask`, and `pearson`. `K_to` is the higher K. `n_mask` is how many people were used in the match. The pearson field is one token per display column, and a trailing unmatched column is left off, so the step to K=3 has two numbers.

```text
K_to	n_mask	pearson
3	2448	0.995 0.748
```

The first rows of `order.tsv`:

```text
rank	iid	group
1	106-A	C-Ad
2	13	C-Ad
3	136	C-Ad
4	14-A	C-Ad
```

`blocks.tsv`:

```text
group	start	end	n
C-Ad	1	534	534
CG1	535	877	343
CG2	878	973	96
CG3	974	1090	117
CG4	1091	1336	246
CG5	1337	1473	137
CG6	1474	1602	129
W-Ad	1603	1991	389
WEE1	1992	2089	98
WEE2	2090	2170	81
WWE1	2171	2336	166
WWE2	2337	2448	112
```

## (c) Choosing an alignment method

Do this when you want to see whether another match changes the column order. If you skip it, the run keeps greedy, which is the method in section (b). [Choosing an alignment method](choosing-alignment-method.md) also describes jaccard.

Pearson correlation here is the correlation between two columns of ancestry proportions across the same people. Greedy walks the old columns in order and takes the unused new column with the highest Pearson correlation.

Hungarian picks a one-to-one match that maximizes the sum of those correlations.

```bash
qbar \
  --q demo/2448/ref2448_pruned.2.Q demo/2448/ref2448_pruned.3.Q \
  --fam demo/2448/ref2448_pruned.fam \
  --groups demo/2448/groups.tsv \
  --id-col id \
  --group-col group \
  --align-method hungarian \
  --outdir out/hungarian
```

```text
K_to	n_mask	pearson
3	2448	0.995 0.748
```

```text
C	raw	hex	owners
C1	3	#4470b7	W-Ad+WWE1+WWE2
C2	1	#dc1f26	CG1+CG2+WEE1+WEE2
C3	2	#981b1e	C-Ad+CG3+CG4+CG5+CG6
```

Pong allows one old column to split into two new columns. Its `align.tsv` adds `pong_sim` and `split_parent`.

```bash
qbar \
  --q demo/2448/ref2448_pruned.2.Q demo/2448/ref2448_pruned.3.Q \
  --fam demo/2448/ref2448_pruned.fam \
  --groups demo/2448/groups.tsv \
  --id-col id \
  --group-col group \
  --align-method pong \
  --outdir out/pong
```

```text
K_to	n_mask	pong_sim	split_parent
3	2448	0.970 0.970	C2
```

```text
C	raw	hex	owners
C1	3	#4470b7	W-Ad+WWE1+WWE2
C2	1	#dc1f26	CG1+CG2+WEE1+WEE2
C3	2	#981b1e	C-Ad+CG3+CG4+CG5+CG6
```

On these demo files, greedy, hungarian, and pong agree. `perm_K3.tsv` from hungarian and from pong has the same `raw` column as the greedy file in section (b), and hungarian's pearson line matches the greedy line. The pong score line is the one above, including `split_parent` `C2`.

They differ when the in-order greedy choice is not the assignment with the largest summed Pearson correlation, or when one old column should be allowed to split into two new columns. [Choosing an alignment method](choosing-alignment-method.md) states which method does which.

## (d) Ordering and groups

Do this when the left-to-right order should follow groups, or a tree inside those groups. If you skip the groups file, every person gets the label `NA` and one block covers the whole plot. If you pass `--groups` and skip `--id-col` and `--group-col`, the run stops before writing the plot.

```bash
qbar \
  --q demo/2448/ref2448_pruned.2.Q demo/2448/ref2448_pruned.3.Q \
  --fam demo/2448/ref2448_pruned.fam \
  --groups demo/2448/groups.tsv \
  --outdir out/nocols
```

```text
The group table has no column analysis_IID / Dong_Grp. Columns present: id, group
```

```bash
qbar \
  --q demo/2448/ref2448_pruned.2.Q demo/2448/ref2448_pruned.3.Q \
  --fam demo/2448/ref2448_pruned.fam \
  --outdir out/nogroups
```

```text
rank	iid	group
1	1	NA
2	1-A	NA
```

```text
group	start	end	n
NA	1	2448	2448
```

`--order-mode group-hclust` keeps each group contiguous. `--group-order hclust` builds a linkage on the mean Q row of each group and takes SciPy's leaf order of that linkage. `--within hclust` orders people inside each group by average linkage and distance 1-Pearson, and writes one `linkage_group_<n>.tsv` per group of at least two people. The default `--within` is `iid`, which sorts people in a group by name and writes no within-group linkage file. If you skip `--within hclust`, that is the order you get. The default run in section (b) did not pass these flags. Its `blocks.tsv` starts with `C-Ad`. The command below writes `linkage_between_groups.tsv`, `linkage_index.tsv`, and `linkage_group_1.tsv` through `linkage_group_12.tsv`. The number in `linkage_group_<n>.tsv` is the 1-based index in `linkage_index.tsv`, which lists groups in the order they first appear. Its `blocks.tsv` starts with `W-Ad`.

```bash
qbar \
  --q demo/2448/ref2448_pruned.2.Q demo/2448/ref2448_pruned.3.Q \
  --fam demo/2448/ref2448_pruned.fam \
  --groups demo/2448/groups.tsv \
  --id-col id \
  --group-col group \
  --order-mode group-hclust \
  --group-order hclust \
  --within hclust \
  --outdir out/order
```

```text
align.tsv
args.txt
bar_K2.pdf
bar_K2.png
bar_K3.pdf
bar_K3.png
blocks.tsv
linkage_between_groups.tsv
linkage_group_1.tsv
linkage_group_10.tsv
linkage_group_11.tsv
linkage_group_12.tsv
linkage_group_2.tsv
linkage_group_3.tsv
linkage_group_4.tsv
linkage_group_5.tsv
linkage_group_6.tsv
linkage_group_7.tsv
linkage_group_8.tsv
linkage_group_9.tsv
linkage_index.tsv
order.tsv
panel.pdf
panel.png
perm_K2.tsv
perm_K3.tsv
```

```text
rank	iid	group
1	IR19	W-Ad
2	ITA46	W-Ad
3	IR27	W-Ad
```

```text
group	start	end	n
W-Ad	1	389	389
WWE2	390	501	112
WWE1	502	667	166
WEE2	668	748	81
CG2	749	844	96
CG1	845	1187	343
WEE1	1188	1285	98
CG6	1286	1414	129
CG3	1415	1531	117
CG5	1532	1668	137
C-Ad	1669	2202	534
CG4	2203	2448	246
```

```text
row	idx1	idx2	distance	count
0	3	11	0.000834	2
```

`linkage_index.tsv` starts:

```text
index	group
1	CG6
2	CG2
3	W-Ad
4	CG1
```

`linkage_group_1.tsv` is the tree for index 1. It starts:

```text
row	idx1	idx2	distance	count
0	12	23	0.000000	2
```

## (e) Palettes

Do this when you want a different colour for an aligned column. If you skip it, the hex column stays the one in section (b).

The section (b) command did not pass `--palette`. Its `perm_K2.tsv` hex values are `#4470b7` and `#dc1f26`. `--palette classic` writes different hex values:

```bash
qbar \
  --q demo/2448/ref2448_pruned.2.Q demo/2448/ref2448_pruned.3.Q \
  --fam demo/2448/ref2448_pruned.fam \
  --groups demo/2448/groups.tsv \
  --id-col id \
  --group-col group \
  --palette classic \
  --outdir out/classic
```

```text
C	raw	hex	owners
C1	1	#0072b2	W-Ad+WWE1+WWE2
C2	2	#d55e00	C-Ad+CG1+CG2+CG3+CG4+CG5+CG6+WEE1+WEE2
```

```text
C	raw	hex	owners
C1	3	#0072b2	W-Ad+WWE1+WWE2
C2	1	#d55e00	CG1+CG2+WEE1+WEE2
C3	2	#009e73	C-Ad+CG3+CG4+CG5+CG6
```

`--color` is `name=#rrggbb`, split at the first equals sign. The name can be a group or an aligned column such as `C3`. This command sets the group `WWE1` to `#112233`. In the files below, aligned column `C1` has that hex at both K.

```bash
qbar \
  --q demo/2448/ref2448_pruned.2.Q demo/2448/ref2448_pruned.3.Q \
  --fam demo/2448/ref2448_pruned.fam \
  --groups demo/2448/groups.tsv \
  --id-col id \
  --group-col group \
  --color WWE1=#112233 \
  --outdir out/color
```

```text
C	raw	hex	owners
C1	1	#112233	W-Ad+WWE1+WWE2
C2	2	#dc1f26	C-Ad+CG1+CG2+CG3+CG4+CG5+CG6+WEE1+WEE2
```

```text
C	raw	hex	owners
C1	3	#112233	W-Ad+WWE1+WWE2
C2	1	#dc1f26	CG1+CG2+WEE1+WEE2
C3	2	#981b1e	C-Ad+CG3+CG4+CG5+CG6
```

Section (h) records `"palette": "science"` for a command that does not pass `--palette`.

## (f) Uncertainty

Do this when you want a count of how often the column match returns. If you skip `--bootstrap`, the run does not write `match_support.tsv`. The file list in section (b) has no `match_support.tsv`.

`--bootstrap 100` resamples rows 100 times with `--bootstrap-seed 0` and writes one row per aligned column. `support` on each row of this run is `1.000000`. These columns describe the match under that resampling. They do not show that an ancestral population existed.

```bash
qbar \
  --q demo/2448/ref2448_pruned.2.Q demo/2448/ref2448_pruned.3.Q \
  --fam demo/2448/ref2448_pruned.fam \
  --groups demo/2448/groups.tsv \
  --id-col id \
  --group-col group \
  --bootstrap 100 \
  --bootstrap-seed 0 \
  --outdir out/boot
```

```text
K_to	aligned_column	raw_column	n_boot	n_same	support	seed	method	n_empty_mask
3	C1	3	100	100	1.000000	0	greedy	0
3	C2	1	100	100	1.000000	0	greedy	0
3	C3	2	100	100	1.000000	0	greedy	0
```

That command omitted `--perm`. The file has no permutation columns: no `n_perm`, `n_extreme`, `p`, `null`, or `zero_column`.

`--perm` counts a null distribution for the match. If you set `--perm` above 0 and skip `--perm-null`, the run stops:

```bash
qbar \
  --q demo/2448/ref2448_pruned.2.Q demo/2448/ref2448_pruned.3.Q \
  --fam demo/2448/ref2448_pruned.fam \
  --groups demo/2448/groups.tsv \
  --id-col id \
  --group-col group \
  --perm 100 \
  --outdir out/perm-nonull
```

```text
--perm requires --perm-null when --perm is greater than 0. Choices are rows and column.
```

`--perm-null rows` shuffles the row order of the higher K and reruns that match. With `--perm 100` and `--perm-seed 0`, and without `--bootstrap`, the bootstrap columns are `NA` and the file adds `n_perm`, `n_extreme`, `p`, `null`, and `zero_column`.

```bash
qbar \
  --q demo/2448/ref2448_pruned.2.Q demo/2448/ref2448_pruned.3.Q \
  --fam demo/2448/ref2448_pruned.fam \
  --groups demo/2448/groups.tsv \
  --id-col id \
  --group-col group \
  --perm 100 \
  --perm-null rows \
  --perm-seed 0 \
  --outdir out/perm
```

```text
K_to	aligned_column	raw_column	n_boot	n_same	support	seed	method	n_empty_mask	n_perm	n_extreme	p	null	zero_column
3	C1	3	NA	NA	NA	NA	greedy	NA	100	0	0.009901	rows	no
3	C2	1	NA	NA	NA	NA	greedy	NA	100	0	0.009901	rows	no
3	C3	2	NA	NA	NA	NA	greedy	NA	100	NA	NA	rows	no
```

Under the rows null, T is the unrounded Pearson the greedy matcher returns for that column. A small p means that score is in the upper tail of the shuffled scores. On these K=2 and K=3 files, n_extreme is 0, 0, and NA, and the p values are 0.009901, 0.009901, and NA. The same flags on `demo/2448/ref2448_pruned.11.Q` and `demo/2448/ref2448_pruned.12.Q` give twelve p values, in column order: 0.009901, 0.009901, 0.009901, 0.009901, 0.009901, 0.009901, 0.009901, 0.009901, 0.009901, 0.009901, 0.009901, and NA. A large p under rows does not mean the match is wrong. The match strength is the Pearson values in `align.tsv` and the `support` column from `--bootstrap`. This rows run writes Pearson `0.995 0.748`. The K=11 to K=12 rows run writes Pearson `1.000 1.000 1.000 1.000 0.991 1.000 1.000 0.996 0.999 0.848 1.000`.

The command below is that K=11 to K=12 rows run. If you skip it, the K=3 table above is the only rows example on this page. The table has twelve data rows. The first two are copied here.

```bash
qbar \
  --q demo/2448/ref2448_pruned.11.Q demo/2448/ref2448_pruned.12.Q \
  --fam demo/2448/ref2448_pruned.fam \
  --groups demo/2448/groups.tsv \
  --id-col id \
  --group-col group \
  --perm 100 \
  --perm-null rows \
  --perm-seed 0 \
  --outdir out/perm-k12
```

```text
K_to	n_mask	pearson
12	2448	1.000 1.000 1.000 1.000 0.991 1.000 1.000 0.996 0.999 0.848 1.000
```

```text
K_to	aligned_column	raw_column	n_boot	n_same	support	seed	method	n_empty_mask	n_perm	n_extreme	p	null	zero_column
12	C1	10	NA	NA	NA	NA	greedy	NA	100	0	0.009901	rows	no
12	C2	9	NA	NA	NA	NA	greedy	NA	100	0	0.009901	rows	no
```

`--perm-null column` permutes one new column's entries across individuals and recomputes that column's similarity to its matched old column, which breaks the constraint that a row sums to 1. If you skip it, the page only shows the rows null.

```bash
qbar \
  --q demo/2448/ref2448_pruned.2.Q demo/2448/ref2448_pruned.3.Q \
  --fam demo/2448/ref2448_pruned.fam \
  --groups demo/2448/groups.tsv \
  --id-col id \
  --group-col group \
  --perm 100 \
  --perm-null column \
  --perm-seed 0 \
  --outdir out/perm-column
```

```text
K_to	n_mask	pearson
3	2448	0.995 0.748
```

```text
K_to	aligned_column	raw_column	n_boot	n_same	support	seed	method	n_empty_mask	n_perm	n_extreme	p	null	zero_column
3	C1	3	NA	NA	NA	NA	greedy	NA	100	0	0.009901	column	no
3	C2	1	NA	NA	NA	NA	greedy	NA	100	0	0.009901	column	no
3	C3	2	NA	NA	NA	NA	greedy	NA	100	NA	NA	column	no
```

`C3` is the leftover column, so `p` and `n_extreme` are `NA`. A small p is a tail probability under the chosen null. It is not evidence that the index is the true ancestry label.

## (g) Replicates

`--replicates` groups several Q files at one K. The bundled demo has one Q file at each K from 2 through 12, named `ref2448_pruned.2.Q` through `ref2448_pruned.12.Q`, and no second file at the same K. This walk-through does not pass `--replicates`. If you skip it on this demo, there is nothing to group. The flag and the required `--mode-sim-cut` are in [the replicates note](factpacks/S1.md).

## (h) HTML, the editor, and replay

Do this when you want one offline page for the bars, and a second page that can change the order and the colours, plus a file you can run again. If you skip `--html`, the run does not write `panel.html`. If you skip `--editor`, it does not write `editor.html` or `state.json`. If you skip `--state`, the order is the one from the ordering rules, which is the run in section (b).

```bash
qbar \
  --q demo/2448/ref2448_pruned.2.Q demo/2448/ref2448_pruned.3.Q \
  --fam demo/2448/ref2448_pruned.fam \
  --groups demo/2448/groups.tsv \
  --id-col id \
  --group-col group \
  --html \
  --editor \
  --outdir out/editor
```

```text
align.tsv
args.txt
bar_K2.pdf
bar_K2.png
bar_K3.pdf
bar_K3.png
blocks.tsv
editor.html
order.tsv
panel.html
panel.pdf
panel.png
perm_K2.tsv
perm_K3.tsv
state.json
```

The panel page starts:

```text
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>qbar panel</title>
```

The editor page has `<title>qbar editor</title>`. What the page can change is in [the editor note](factpacks/F9.md).

`state.json` begins:

```text
  "schema": "qbar-state",
  "schema_version": 1,
  "qbar_version": "0.3.0",
```

The `plot` object records the options this command did not pass, including palette `science`, width `2200`, bar height `0`, qmax `0.75`, and an empty title:

```text
  "plot": {
    "align": true,
    "align_mode": "all",
    "anchor_group": "",
    "align_groups": "",
    "qmax": 0.75,
    "jaccard_set": "dominant",
    "jaccard_cut": 0.5,
    "palette": "science",
    "color_lock": "off",
    "order_mode": "within",
    "group_order_flag": "input",
    "within": "iid",
    "rest_name": "NA",
    "blocks": "",
    "q_format": "admixture",
    "replicates": false,
    "mode_sim_cut": null,
    "width": 2200,
    "bar_height": 0,
    "title": ""
  },
```

Replay reads that file after the usual alignment and then uses its order and colours. This file was just written and was not edited, so the replay is the same order as the editor run. The replay command does not pass `--editor`, and it does not write a new `state.json`.

```bash
qbar \
  --q demo/2448/ref2448_pruned.2.Q demo/2448/ref2448_pruned.3.Q \
  --fam demo/2448/ref2448_pruned.fam \
  --groups demo/2448/groups.tsv \
  --id-col id \
  --group-col group \
  --state out/editor/state.json \
  --outdir out/replay
```

```text
align.tsv
args.txt
bar_K2.pdf
bar_K2.png
bar_K3.pdf
bar_K3.png
blocks.tsv
order.tsv
panel.pdf
panel.png
perm_K2.tsv
perm_K3.tsv
```

```text
rank	iid	group
1	106-A	C-Ad
2	13	C-Ad
```

## (i) Config file

Do this when you want the paths in a file. If you skip `--config`, you pass the same paths on the command line, as the earlier sections do. Reading the file needs the extra `qbar[config]` (PyYAML). The core install does not include it.

Save this as `tutorial.yaml` in the repository root. Paths are resolved from the working directory.

```yaml
q:
  - demo/2448/ref2448_pruned.2.Q
  - demo/2448/ref2448_pruned.3.Q
fam: demo/2448/ref2448_pruned.fam
groups: demo/2448/groups.tsv
id_col: id
group_col: group
outdir: out/config
```

Without that extra, the command stops:

```bash
qbar --config tutorial.yaml
```

```text
Reading --config needs PyYAML. Install it with pip install "qbar[config]".
```

After that install, the same command writes `config_resolved.json`. The file records the base names, and `sources` says which values came from the file:

```bash
qbar --config tutorial.yaml
```

```text
config_resolved.json
```

```text
  "config_file": "tutorial.yaml",
```

```text
  "fam": "ref2448_pruned.fam",
```

```text
  "id_col": "id",
```

```text
  "palette": "science",
```

```text
    "fam": "config",
    "flow_weight": "default",
    "greyscale_preview": "default",
    "group_col": "config",
    "group_order": "default",
    "groups": "config",
    "hclust_dist": "default",
    "hclust_k": "default",
    "hclust_linkage": "default",
    "hclust_max_bytes": "default",
    "hclust_olo": "default",
    "hclust_pre": "default",
    "html": "default",
    "id_col": "config",
```

## (j) Exports

Do this when another program should read the aligned Q. If you skip `--export`, the run writes no `export` directory. The section (b) file list has no `export/` path.

```bash
qbar \
  --q demo/2448/ref2448_pruned.2.Q demo/2448/ref2448_pruned.3.Q \
  --fam demo/2448/ref2448_pruned.fam \
  --groups demo/2448/groups.tsv \
  --id-col id \
  --group-col group \
  --export clumpp,pong \
  --outdir out/export
```

```text
align.tsv
args.txt
bar_K2.pdf
bar_K2.png
bar_K3.pdf
bar_K3.png
blocks.tsv
export/clumpp/K2.indfile
export/clumpp/K2.popq
export/clumpp/K3.indfile
export/clumpp/K3.popq
export/clumpp/ids.tsv
export/clumpp/names.txt
export/pong/K2.Q
export/pong/K3.Q
export/pong/filemap.txt
export/pong/ind2pop.txt
order.tsv
panel.pdf
panel.png
perm_K2.tsv
perm_K3.tsv
```

`export/clumpp/ids.tsv` starts:

```text
index	iid
1	106-A
2	13
3	136
```

`export/clumpp/names.txt`:

```text
1 C-Ad
2 CG1
3 CG2
4 CG3
5 CG4
6 CG5
7 CG6
8 W-Ad
9 WEE1
10 WEE2
11 WWE1
12 WWE2
```

The first data line of `export/clumpp/K2.indfile`:

```text
1 1 1 1 : 0.025532 0.974468
```

`export/pong/filemap.txt`:

```text
qbar_K2	2	K2.Q
qbar_K3	3	K3.Q
```

This walk-through did not run CLUMPP, DISTRUCT, or pong. [The export note](factpacks/S12.md) records that no CLUMPP, DISTRUCT, or pong binary was executed on the export files.

## (k) The web page

Do this when you want the same package in a browser. If you skip it, you stay with the commands above. The page, the build, and the local server are described in [the web page note](web.md). This walk-through does not build or serve the page. The commands copied from that note are:

```bash
python tools/build_web.py
```

```bash
python -m http.server --directory web 8000
```
