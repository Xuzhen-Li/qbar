# qbar

[中文](README.zh.md)

qbar is a command-line tool that reads ADMIXTURE Q matrix files (.Q), sorts samples, aligns columns across K values, and draws population structure bar plots in PNG and PDF formats. An ADMIXTURE Q matrix file is a table that shows how much of each sample's genetic makeup comes from each ancestral group, where K is the number of ancestral groups tested. A population structure bar plot draws each sample as a vertical bar split into colored segments for those ancestral proportions, and aligning columns keeps the colors consistent from K-1 to K. Everything runs from one script: `python3 qbar.py`.

![Demo panel](docs/img/a_demo_panel.png)

## Before you start

To run qbar, you need to open a terminal, which is a text window where you type commands to control your computer. On macOS, open the Terminal app; on Linux, open a Linux terminal; on Windows, use WSL (Windows Subsystem for Linux, a feature that lets you run a Linux terminal on Windows). After opening the terminal, go to the qbar folder and type your commands there.

## Install

qbar needs Python 3, numpy, and Pillow. scipy is needed only for `--within hclust` or `--within-group X=hclust` (and all `--hclust-*` options), and for `--align-method` `hungarian`, `pong` and `jaccard`. Hclust (hierarchical clustering) groups similar samples together automatically, while alignment methods like greedy, hungarian, pong, and jaccard are different mathematical ways to match ancestral group columns from K-1 to K. Default greedy alignment and everything else need only numpy and Pillow, though scipy is already in `requirements.txt`.

```bash
git clone https://github.com/Xuzhen-Li/qbar.git
cd qbar
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -r requirements.txt
```

qbar was tested on Python 3.13.5, numpy 2.5.4, Pillow 12.3.0, and scipy 1.18.1. You can run the self-check to verify that the program works on your machine:

```bash
python3 test_qbar.py
```

44 tests pass. New features do not change defaults: with no new options, results are the same as before.

## Input files

The first input is a Q matrix (`.Q`) with ancestry proportions, which has one row per person. Ancestry proportions are numbers that add up to 1 across each row and tell what fraction of a person's genetic makeup comes from each ancestral group. qbar rejects a loaded value only when it is below -1e-6 or above 1+1e-4. A row is still drawn, with a warning, when abs(sum - 1) > 0.05 on the loaded floats.

```text
0.048906 0.126240 0.516154 0.158683 0.000010 0.002808 0.000010 0.147189
0.000010 0.856385 0.015772 0.055593 0.052034 0.000010 0.000010 0.020186
0.000010 0.199419 0.000010 0.770174 0.000010 0.000010 0.000010 0.030357
0.060011 0.000010 0.888786 0.000010 0.013514 0.018525 0.019134 0.000010
0.129499 0.643154 0.000010 0.000010 0.019487 0.091643 0.000010 0.116187
```

The second input gives sample IDs either from a PLINK `.fam` file (where the IID is in column 2) via `--fam`, or from a plain list with one IID per line via `--ids`; use one of these options, not both. A PLINK `.fam` file is a standard genetics table of sample information, and an IID (individual identifier) is the unique name for one sample.

```text
1 1 0 0 0 -9
1-A 1-A 0 0 0 -9
1-W 1-W 0 0 0 -9
10 10 0 0 0 -9
10-A 10-A 0 0 0 -9
```

The third input is a groups table in tsv or csv format with a header row passed via `--groups`, with `--id-col` and `--group-col` naming the columns for sample IDs and group names. A tsv (tab-separated values) file splits columns with tabs, a csv (comma-separated values) file splits columns with commas, and a header row is the first line that gives each column its name.

```text
id	group
1	CG6
1-A	CG2
1-W	W-Ad
10	CG6
```

## Quick start

This quick start runs the bundled 2448-sample demo with K from 2 to 12. Make sure to quote wildcards in your command, and run it from the qbar folder. A wildcard is a symbol like `*` that matches multiple file names at once, and putting quotes around it lets qbar expand the file list itself.

```bash
python3 qbar.py \
  --q 'demo/2448/ref2448_pruned.*.Q' \
  --fam demo/2448/ref2448_pruned.fam \
  --groups demo/2448/groups.tsv --id-col id --group-col group \
  --blocks C-Ad,CG1,CG2,CG3,CG4,CG5,CG6,W-Ad,WEE1,WEE2,WWE1,WWE2 \
  --within iid \
  --anchor-group WWE1 \
  --color WWE1=#4470b7 --color WEE1=#dc1f26 --color WEE2=#0b5475 \
  --color CG6=#981b1e --color CG4=#f7922c --color CG3=#835ca6 \
  --color CG5=#fbee61 --color WWE2=#f6a3b1 \
  --outdir demo/out
```

The terminal shows the following output:

```text
demo/out/panel.png
order	demo/out/order.tsv
```

## Output

All results are saved in the folder set by `--outdir`. `panel.png` and `panel.pdf` show all K values stacked together in one figure, while `bar_K*.png` and `bar_K*.pdf` show the bar plot for one K at a time. `order.tsv` lists the final sample order from left to right, and `blocks.tsv` records the start and end positions of each group block on the plot. `align.tsv` gives the alignment scores between K values, `perm_K*.tsv` maps each raw column to its aligned column, and `args.txt` saves the full command you ran. `align_report.tsv` and `align_report.txt` appear only when you add `--align-report`.

* `--align` forces cross-K alignment on. Omitting both `--align` and `--no-align` does the same when two or more K files are given.
* `--color-file` is a text file of two whitespace-separated columns: a name and `#rrggbb`.
* `--title` is drawn above the figure. The default is empty, which draws no title.
* `--width` is the bar width in pixels. The default is 2200.
* `--bar-height` is the height in pixels of one K row. The default is 0, which means 220 for a single K and 120 when several K are drawn.

If you give a single `.Q` file, qbar writes only `bar_K8.png` and `bar_K8.pdf` for that K, with no panel image and no `align.tsv`:

```bash
python3 qbar.py --q demo/2448/ref2448_pruned.8.Q --fam demo/2448/ref2448_pruned.fam --groups demo/2448/groups.tsv --id-col id --group-col group --blocks C-Ad,CG1,CG2,CG3,CG4,CG5,CG6,W-Ad,WEE1,WEE2,WWE1,WWE2 --within iid --color WWE1=#4470b7 --color WEE1=#dc1f26 --color WEE2=#0b5475 --color CG6=#981b1e --color CG4=#f7922c --color CG3=#835ca6 --color CG5=#fbee61 --color WWE2=#f6a3b1 --outdir out/b_singleK8
```

![Single K8](docs/img/b_single_K8.png)

## Sorting

`--order-file` takes a file with one IID per line, fixes the left-to-right sample order, and overrides `--blocks`. `--blocks` is a comma list of groups from left to right; any groups not listed are appended in alphabetical order. A group name cannot contain a comma, because a comma splits one name into two blocks. People without a group get the label from `--rest-name` (default `NA`).

The `--within` option (default `iid`) controls how samples are sorted inside each group:

* `iid`: sort samples alphabetically by ID.
* `q`: sort by the person's highest component in descending order. Descending order puts the largest numbers first, from highest to lowest.
* `hclust`: run hierarchical clustering inside the group (needs scipy). Hierarchical clustering builds a tree that groups people with similar ancestry numbers next to each other.
* `input`: keep the original Q file row order.

`--within-group G=method` sets a sorting method for one specific group `G` and is repeatable for multiple groups. `--sort-col N` (1-based, aligned `C1`, `C2`, ...) makes `q` groups sort by that specific column; 1-based means the first column is numbered 1 rather than 0. `--sort-k` picks the K value used for sorting (default is the largest K).

### Within-group clustering options

These clustering options apply wherever `hclust` is used:

* `--hclust-dist` accepts `correlation` (default, 1 minus Pearson), `euclidean`, or `braycurtis`. A distance measure calculates a single number telling how different two people's ancestry proportions are from each other. `braycurtis` gives `NaN` distances for people whose values are all zero (`NaN` stands for "not a number", which happens when a calculation divides by zero).
* `--hclust-linkage` accepts `average` (default), `ward`, or `complete`. A linkage rule decides how to measure the distance between two sub-clusters of people when merging them into a tree. `ward` requires `--hclust-dist euclidean`, otherwise qbar stops at start, even if no group uses `hclust`.
* `--hclust-olo` (off by default) reorders leaves with optimal leaf ordering on the same distance (Bar-Joseph et al. 2001). Leaves are the individual samples at the tips of the clustering tree, and optimal leaf ordering flips tree branches so adjacent samples are as similar as possible.
* `--hclust-pre dominant` (default `none`) first splits each group by each person's highest column (with ties going to the lower column number), places those sub-blocks in order `C1`, `C2`, ..., and then clusters inside each block. It uses aligned columns, so it depends on alignment and `--anchor-group`.

All clustering steps are computed on one K (`--hclust-k`, which defaults to `--sort-k`); that resulting order is used at every K, so the sample order is the same across K. The defaults give the previous order exactly.

For more details on the underlying clustering methods, see [https://docs.scipy.org/doc/scipy/reference/generated/scipy.cluster.hierarchy.linkage.html](https://docs.scipy.org/doc/scipy/reference/generated/scipy.cluster.hierarchy.linkage.html) and [https://docs.scipy.org/doc/scipy/reference/generated/scipy.cluster.hierarchy.optimal_leaf_ordering.html](https://docs.scipy.org/doc/scipy/reference/generated/scipy.cluster.hierarchy.optimal_leaf_ordering.html).

### Clustering examples

These examples run `demo/2448` with K from 2 to 6 and `--within hclust`, and compare how many people out of 2448 change position versus the default (`euclidean` 2417, `braycurtis` 2424, `ward` 2419, `complete` 2423, `olo` 2391, `pre dominant` 1516).

The default setting uses `correlation` distance and `average` linkage to cluster people inside each group. `correlation` distance compares the overall shape of two people's ancestry patterns, and `average` linkage measures the average distance between all pairs of people in two clusters.

```bash
python3 qbar.py --q 'demo/2448/ref2448_pruned.[2-6].Q' --fam demo/2448/ref2448_pruned.fam --groups demo/2448/groups.tsv --id-col id --group-col group --blocks C-Ad,CG1,CG2,CG3,CG4,CG5,CG6,W-Ad,WEE1,WEE2,WWE1,WWE2 --within hclust --anchor-group WWE1 --outdir out/d_hclust
```

![Default (correlation, average)](docs/img/d_within_hclust.png)

Using `euclidean` distance changes the position of 2417 out of 2448 people compared to the default. `euclidean` distance is the straight-line geometric distance between two people's ancestry proportion values.

```bash
python3 qbar.py --q 'demo/2448/ref2448_pruned.[2-6].Q' --fam demo/2448/ref2448_pruned.fam --groups demo/2448/groups.tsv --id-col id --group-col group --blocks C-Ad,CG1,CG2,CG3,CG4,CG5,CG6,W-Ad,WEE1,WEE2,WWE1,WWE2 --within hclust --hclust-dist euclidean --anchor-group WWE1 --outdir out/k_hc_euclidean
```

![euclidean distance](docs/img/k_hclust_euclidean.png)

Using `braycurtis` distance changes the position of 2424 out of 2448 people compared to the default. `braycurtis` distance adds up the absolute differences between two people's ancestry proportions and divides by their total sum.

```bash
python3 qbar.py --q 'demo/2448/ref2448_pruned.[2-6].Q' --fam demo/2448/ref2448_pruned.fam --groups demo/2448/groups.tsv --id-col id --group-col group --blocks C-Ad,CG1,CG2,CG3,CG4,CG5,CG6,W-Ad,WEE1,WEE2,WWE1,WWE2 --within hclust --anchor-group WWE1 --hclust-dist braycurtis --outdir out/k_hc_braycurtis
```

![braycurtis distance](docs/img/k_hclust_braycurtis.png)

Using `ward` linkage (which needs `euclidean` distance) changes the position of 2419 out of 2448 people compared to the default. `ward` linkage merges the two clusters that give the smallest increase in total within-cluster variance.

```bash
python3 qbar.py --q 'demo/2448/ref2448_pruned.[2-6].Q' --fam demo/2448/ref2448_pruned.fam --groups demo/2448/groups.tsv --id-col id --group-col group --blocks C-Ad,CG1,CG2,CG3,CG4,CG5,CG6,W-Ad,WEE1,WEE2,WWE1,WWE2 --within hclust --anchor-group WWE1 --hclust-dist euclidean --hclust-linkage ward --outdir out/k_hc_ward
```

![ward linkage (needs euclidean)](docs/img/k_hclust_ward.png)

Using `complete` linkage changes the position of 2423 out of 2448 people compared to the default. `complete` linkage measures the distance between two clusters using the two farthest people in those clusters.

```bash
python3 qbar.py --q 'demo/2448/ref2448_pruned.[2-6].Q' --fam demo/2448/ref2448_pruned.fam --groups demo/2448/groups.tsv --id-col id --group-col group --blocks C-Ad,CG1,CG2,CG3,CG4,CG5,CG6,W-Ad,WEE1,WEE2,WWE1,WWE2 --within hclust --anchor-group WWE1 --hclust-linkage complete --outdir out/k_hc_complete
```

![complete linkage](docs/img/k_hclust_complete.png)

Using optimal leaf ordering (`--hclust-olo`) changes the position of 2391 out of 2448 people compared to the default. Optimal leaf ordering flips branches of the clustering tree so that neighboring people in the final list are as similar as possible.

```bash
python3 qbar.py --q 'demo/2448/ref2448_pruned.[2-6].Q' --fam demo/2448/ref2448_pruned.fam --groups demo/2448/groups.tsv --id-col id --group-col group --blocks C-Ad,CG1,CG2,CG3,CG4,CG5,CG6,W-Ad,WEE1,WEE2,WWE1,WWE2 --within hclust --anchor-group WWE1 --hclust-olo --outdir out/k_hc_olo
```

![optimal leaf ordering](docs/img/k_hclust_olo.png)

Using `--hclust-pre dominant` changes the position of 1516 out of 2448 people compared to the default. This pre-split groups people by their largest aligned ancestry column first and then runs hierarchical clustering inside each sub-block.

```bash
python3 qbar.py --q 'demo/2448/ref2448_pruned.[2-6].Q' --fam demo/2448/ref2448_pruned.fam --groups demo/2448/groups.tsv --id-col id --group-col group --blocks C-Ad,CG1,CG2,CG3,CG4,CG5,CG6,W-Ad,WEE1,WEE2,WWE1,WWE2 --within hclust --anchor-group WWE1 --hclust-pre dominant --outdir out/k_hc_pre_dominant
```

![pre dominant split](docs/img/k_hclust_pre_dominant.png)

## Common tasks

To use a custom sample order, pass a file to `--order-file` to fix the left-to-right order of people on the plot. This example uses the bundled `demo/2448/order.txt`; for your own list, write one IID per line.

```text
106-A
13
136
14-A
15-A
```

```bash
python3 qbar.py --q demo/2448/ref2448_pruned.8.Q --fam demo/2448/ref2448_pruned.fam --groups demo/2448/groups.tsv --id-col id --group-col group --order-file demo/2448/order.txt --outdir out
```

Terminal output:

```text
out/bar_K8.png
order	out/order.tsv
```

![Custom order](docs/img/f_order_file.png)

To sort within each group, `--within iid` (the default) sorts people by ID, while `--within hclust` groups people with similar ancestry profiles together (see Clustering examples and Sorting for more options). An ancestry profile is the complete set of ancestry proportions for one person across all columns at a given K.

```bash
python3 qbar.py --q 'demo/2448/ref2448_pruned.[2-6].Q' --fam demo/2448/ref2448_pruned.fam --groups demo/2448/groups.tsv --id-col id --group-col group --blocks C-Ad,CG1,CG2,CG3,CG4,CG5,CG6,W-Ad,WEE1,WEE2,WWE1,WWE2 --within iid --anchor-group WWE1 --outdir out/d_iid
```

![Within iid](docs/img/d_within_iid.png)

To set custom colors, pass `--color` with group names (`NAME=#rrggbb`) or aligned column names (`C3=#rrggbb`). The text before the first `=` is the name, so a group name cannot contain `=`. A `#rrggbb` code is a six-digit hexadecimal color code that specifies exact amounts of red, green, and blue.

```bash
python3 qbar.py --q 'demo/2448/ref2448_pruned.[2-6].Q' --fam demo/2448/ref2448_pruned.fam --groups demo/2448/groups.tsv --id-col id --group-col group --blocks C-Ad,CG1,CG2,CG3,CG4,CG5,CG6,W-Ad,WEE1,WEE2,WWE1,WWE2 --within q --anchor-group WWE1 --color WWE1=#4470b7 --color WEE1=#dc1f26 --color CG4=#f7922c --color C3=#2ca02c --outdir out/e_color
```

![Custom colors](docs/img/e_color.png)

To keep the raw ADMIXTURE column order without cross-K alignment, add `--no-align`. Cross-K alignment is the step that matches ancestral group columns from K-1 to K so each ancestral group keeps the same color across rows.

```bash
python3 qbar.py --q 'demo/2448/ref2448_pruned.[2-6].Q' --fam demo/2448/ref2448_pruned.fam --groups demo/2448/groups.tsv --id-col id --group-col group --blocks C-Ad,CG1,CG2,CG3,CG4,CG5,CG6,W-Ad,WEE1,WEE2,WWE1,WWE2 --within iid --no-align --outdir out/c_noalign
```

![No align](docs/img/c_no_align.png)

## Column alignment

When you provide 2 or more K values, columns are aligned across K (this is on by default, while `--no-align` keeps the raw order). Alignment works stepwise from K-1 to K: old columns are matched to new ones, and the leftover new column becomes the new last column. `--align-mode all` (default) uses all people from `--align-groups`, or everyone if that option is not set; `core` keeps only people whose highest ancestry value is above `--qmax` (default `0.75`) at both K values. `--anchor-group G` puts the main column of group `G`'s purest person at `C1` at the lowest K. A purest person is the sample with the highest proportion in a single ancestry column.

### Choosing an alignment method

`--align-method` accepts `greedy`, `hungarian`, `pong`, or `jaccard`. `greedy` is the default, and all methods use the same set of people.

* `greedy`: goes through `C1`, `C2`, ... in order and picks the unused new column with the highest Pearson r, breaking ties by picking the lower column index, and warns on `stderr` when Pearson is less than 0.5. Pearson r (correlation coefficient) is a number from -1 to 1 that measures how closely two columns of numbers follow the same pattern, and `stderr` (standard error) is the terminal text stream used for warning messages. It is fast and works fine when columns clearly match, though the starting column order can affect the result.
* `hungarian`: finds the best overall one-to-one Pearson match across all columns at once. A one-to-one match pairs each old column with a unique new column to maximize the total correlation score. Use it when `greedy` warns about a low Pearson score or when two columns compete for the same match; it gives the same order as `greedy` on the demo.
* `pong`: follows the idea of Behr et al. 2016, using qbar's own implementation rather than pong's code. It computes similarity from pong manual eq. 1 over people with `a_i + b_i > 0` (pong's code instead uses people with a value of at least `0.1/K`), where `a_i` and `b_i` are a person's ancestry values in the two columns being compared. It tests every pair of new columns as a single merged column; the old column matched to the winning pair is the split parent, and which half keeps the parent's place follows qbar's own convention. Its `align.tsv` columns are `K_to`, `n_mask`, `pong_sim`, and `split_parent`, and it prints no Pearson warning. Use it when one ancestral component splits in two from K-1 to K; it gives the same order as `greedy` on the demo.
* `jaccard`: qbar's own method that matches columns by who is mostly in each column. `--jaccard-set` can be `dominant` (default, the set of people whose highest column is that column) or `threshold` (people with membership at least `--jaccard-cut`, default `0.5`); the Jaccard score is the number of shared people divided by all people in either set. Its `align.tsv` columns are `K_to`, `n_mask`, and `jaccard`. In contrast to tools like CLUMPAK and CLUMPP, which align by full Q-matrix similarity, `jaccard` uses member-set overlap (counting shared people rather than comparing exact ancestry fractions). One caveat is that with `--anchor-group`, the anchored component can leave `C1` (in the demo from K10 to K12, `W-Ad` stays at `C1` while `WWE1` becomes `C10`). Try `threshold` when many people are admixed (meaning their ancestry is split across multiple groups).

As general advice, run the default first, then compare other methods with `--align-report`; if they agree, keep the default.

### Alignment examples

These examples run `demo/2448` with K from 2 to 12. Both `hungarian` and `pong` give the exact same column order as the default `greedy` method at every K, while `jaccard` (under both set types) equals the default at K3 to K9 and swaps `C1` and `C10` at K10 through K12.

Using `--align-method hungarian` finds the best overall one-to-one match across all columns at each step from K-1 to K, and gives the same column order as `greedy` at every K on this dataset.

```bash
python3 qbar.py --q 'demo/2448/ref2448_pruned.*.Q' --fam demo/2448/ref2448_pruned.fam --groups demo/2448/groups.tsv --id-col id --group-col group --blocks C-Ad,CG1,CG2,CG3,CG4,CG5,CG6,W-Ad,WEE1,WEE2,WWE1,WWE2 --within iid --anchor-group WWE1 --color WWE1=#4470b7 --color WEE1=#dc1f26 --color WEE2=#0b5475 --color CG6=#981b1e --color CG4=#f7922c --color CG3=#835ca6 --color CG5=#fbee61 --color WWE2=#f6a3b1 --align-method hungarian --outdir out/g_hungarian
```

![hungarian](docs/img/g_align_hungarian.png)

Using `--align-method pong` gives the same column order as `greedy` at every K and records the split parents across K (`K3` `C2`, `K4` `C3`, `K5` `C3`, `K6` `C2`, `K7` `C3`, `K8` `C2`, `K9` `C1`, `K10` `C1`, `K11` `C6`, `K12` `C4`). A split parent is the ancestral column at K-1 that divides into two new columns at K.

```bash
python3 qbar.py --q 'demo/2448/ref2448_pruned.*.Q' --fam demo/2448/ref2448_pruned.fam --groups demo/2448/groups.tsv --id-col id --group-col group --blocks C-Ad,CG1,CG2,CG3,CG4,CG5,CG6,W-Ad,WEE1,WEE2,WWE1,WWE2 --within iid --anchor-group WWE1 --color WWE1=#4470b7 --color WEE1=#dc1f26 --color WEE2=#0b5475 --color CG6=#981b1e --color CG4=#f7922c --color CG3=#835ca6 --color CG5=#fbee61 --color WWE2=#f6a3b1 --align-method pong --outdir out/h_pong
```

![pong](docs/img/h_align_pong.png)

Using `--align-method jaccard` with the default dominant set type matches columns by the overlap of people whose highest ancestry proportion is in each column, equaling the default greedy method at K3 to K9 and swapping `C1` and `C10` from K10 through K12.

```bash
python3 qbar.py --q 'demo/2448/ref2448_pruned.*.Q' --fam demo/2448/ref2448_pruned.fam --groups demo/2448/groups.tsv --id-col id --group-col group --blocks C-Ad,CG1,CG2,CG3,CG4,CG5,CG6,W-Ad,WEE1,WEE2,WWE1,WWE2 --within iid --anchor-group WWE1 --color WWE1=#4470b7 --color WEE1=#dc1f26 --color WEE2=#0b5475 --color CG6=#981b1e --color CG4=#f7922c --color CG3=#835ca6 --color CG5=#fbee61 --color WWE2=#f6a3b1 --align-method jaccard --outdir out/i_jaccard
```

![jaccard (dominant)](docs/img/i_align_jaccard.png)

Using `--align-method jaccard` with `--jaccard-set threshold` and `--jaccard-cut 0.5` matches columns based on people whose ancestry proportion meets or exceeds the cutoff value, producing the same column order changes as the dominant set type.

```bash
python3 qbar.py --q 'demo/2448/ref2448_pruned.*.Q' --fam demo/2448/ref2448_pruned.fam --groups demo/2448/groups.tsv --id-col id --group-col group --blocks C-Ad,CG1,CG2,CG3,CG4,CG5,CG6,W-Ad,WEE1,WEE2,WWE1,WWE2 --within iid --anchor-group WWE1 --color WWE1=#4470b7 --color WEE1=#dc1f26 --color WEE2=#0b5475 --color CG6=#981b1e --color CG4=#f7922c --color CG3=#835ca6 --color CG5=#fbee61 --color WWE2=#f6a3b1 --align-method jaccard --jaccard-set threshold --jaccard-cut 0.5 --outdir out/i_jaccard_thr
```

![jaccard (threshold)](docs/img/i_align_jaccard_threshold.png)

### Reading the alignment report

```bash
python3 qbar.py --q 'demo/2448/ref2448_pruned.*.Q' --fam demo/2448/ref2448_pruned.fam --groups demo/2448/groups.tsv --id-col id --group-col group --blocks C-Ad,CG1,CG2,CG3,CG4,CG5,CG6,W-Ad,WEE1,WEE2,WWE1,WWE2 --within iid --anchor-group WWE1 --color WWE1=#4470b7 --color WEE1=#dc1f26 --color WEE2=#0b5475 --color CG6=#981b1e --color CG4=#f7922c --color CG3=#835ca6 --color CG5=#fbee61 --color WWE2=#f6a3b1 --align-report --outdir out/j_report
```

`--align-report` (off by default) writes `align_report.tsv` and `align_report.txt` next to `align.tsv` when you have 2 or more K values; it works with all four methods and gives one row per column at each K. The `.txt` file is in English with one block per K step, and to vary the run you can add `--align-method pong --align-report-low 0.8`. For `greedy`, `hungarian`, and `jaccard`, the split parent is the K-1 column with the largest share over the new column, while for `pong` it is the column matched to the split pair, which can differ (in the demo at K4 and K5, `pong` picks `C3` with shares 0.395 and 0.378 versus `C2` with 0.549 and 0.459); ties go to the lower column, if the new column sums to 0 the split fields are `NA`, and shares below about 0.5 are only indicative (such as K6 at 0.414, K7 at 0.385, and K11 at 0.265 versus 0.251). A membership-weighted mean is an average of the K-1 column values where each person is weighted by their value in the new column at K. The low-confidence cuts of 0.5 (`greedy`, `hungarian`, `jaccard`) and 0.8 (`pong`) are qbar's own rules of thumb, not from a paper, and can be changed with `--align-report-low`; on the demo, `greedy`, `hungarian`, and `pong` have no low-confidence rows, while `jaccard` flags K8 `C2` (0.496) and K11 `C5` (0.480). This excerpt of `align_report.txt` comes from the `demo/2448` quick start command plus `--align-report` using the default `greedy` method:

```text
Alignment report
method: greedy (similarity = Pearson r)
low confidence: similarity < 0.5
split parent: K-1 column with the largest membership-weighted mean over the new column

K=2 -> K=3 (people used: 2448)
  C1 <- C1  Pearson r 0.995; top groups: WWE1:0.972;WWE2:0.885;W-Ad:0.684
  C2 <- C2  Pearson r 0.748; top groups: WEE1:0.968;CG1:0.952;CG2:0.699
  C3 new, split from C2 (parent share 0.804; runner-up C1 0.196); top groups: CG6:0.736;CG3:0.609;CG5:0.605
```

Columns in `align_report.tsv`:

* `K_to`: the target K of the step from K-1 to K.
* `column`: the aligned column name (`C1`, `C2`, ...) at `K_to`.
* `raw_column`: the 1-based column number in that K's Q file.
* `matched_from`: the matched `C#` column at K-1, or `new` for the newly added column.
* `method`: the alignment method used (`greedy`, `hungarian`, `pong`, or `jaccard`).
* `similarity`: the match score using the method's own measure.
* `pearson`: the Pearson r score shown for reference.
* `low_confidence`: `yes` if `similarity` is below the cutoff, or `NA` for the new column.
* `split_parent`: the K-1 column that the new column split from.
* `parent_share`: the share of the new column coming from `split_parent`.
* `runner_up`: the K-1 column with the second largest share of the new column.
* `runner_up_share`: the share of the new column coming from `runner_up`.
* `top_groups_mean`: the top 3 groups ranked by their mean (average) value in this column.
* `n_dominant`: the number of people for whom this column is their highest component.
* `top_groups_dominant`: the top groups among the people counted in `n_dominant`.

## Troubleshooting

- `需要 --fam（PLINK .fam）或 --ids（一行一个 IID，顺序与 Q 的行一致）`
  Missing IDs. Provide `--fam` or `--ids`.

- `--fam 和 --ids 只留一个`
  Do not supply both ID sources at once.

- `没有匹配到 Q：demo/nothere/*.Q`
  Wildcard did not match any `.Q` files. Check path and quoting.

- `out/ref.4.Q 文件名是 K=4，列数是 3`
  The columns in the matrix do not match the K integer in the filename.

- `K=3 的 Q 有 100 行，样本名单有 2448 行`
  The number of rows in the Q matrix and the ID list do not match.

- `颜色要写成 #rrggbb，收到 blue`
  Colors must be hex format.

- `锚定组 NOPE 在样本里没有人`
  The group provided to `--anchor-group` does not exist in the data.

- `要跨 K 对齐，K 必须连续。缺 K=3`
  Missing intermediate K values required for sequential cross-K alignment.

- `--sort-col 要在 1 到 3 之间`
  The requested column exceeds available ancestry components for that K.

- `hclust 需要 scipy（scipy.cluster.hierarchy）`
  Install scipy to use `--within hclust`.

- `--align-method hungarian 需要 scipy（scipy.optimize）`
  This error (which names `hungarian`, `pong`, or `jaccard` depending on which method you chose) means you need to install `scipy` with `pip install scipy` (already in `requirements.txt`) or use the default `greedy` method.

- `--hclust-linkage ward 需要 --hclust-dist euclidean，收到 correlation`
  `ward` only works with `euclidean`, so add `--hclust-dist euclidean` or pick `average` or `complete` instead.

## Citation

* For `pong` alignment: Behr AA, Liu KZ, Liu-Fang G, Nakka P, Ramachandran S. Bioinformatics 2016;32(18):2817-2823. [https://doi.org/10.1093/bioinformatics/btw327](https://doi.org/10.1093/bioinformatics/btw327)
* For CLUMPAK (cited only as a contrast for `jaccard`, since CLUMPAK aligns runs by Q-matrix similarity while qbar's `jaccard` uses member-set overlap): Kopelman NM, Mayzel J, Jakobsson M, Rosenberg NA, Mayrose I. Mol Ecol Resour 2015;15(5):1179-1191. [https://doi.org/10.1111/1755-0998.12387](https://doi.org/10.1111/1755-0998.12387)
* For optimal leaf ordering: Bar-Joseph Z, Gifford DK, Jaakkola TS. Bioinformatics 2001;17 Suppl 1:S22-S29. [https://doi.org/10.1093/bioinformatics/17.suppl_1.S22](https://doi.org/10.1093/bioinformatics/17.suppl_1.S22)
* For CLUMPP: Jakobsson and Rosenberg 2007 Bioinformatics 23:1801. [https://doi.org/10.1093/bioinformatics/btm233](https://doi.org/10.1093/bioinformatics/btm233)
* For label switching background (why the same ancestral group can end up in different column numbers across separate runs): Alexander, Novembre and Lange 2009 Genome Res 19:1655. [https://doi.org/10.1101/gr.094052.109](https://doi.org/10.1101/gr.094052.109)
