# qbar

[中文](README.zh.md)

`qbar` reads ADMIXTURE Q matrix files, sorts samples, aligns columns across K values, and plots population genetic structure bar charts.

![Demo panel](docs/img/a_demo_panel.png)

## Install

This tool requires Python 3, numpy, and Pillow. The scipy library is only required when `hclust` sorting is enabled.

[[TODO-TEXT: scipy is now required for `--within hclust` / `--within-group X=hclust` and for `--align-method hungarian`, `pong` and `jaccard` (scipy.optimize.linear_sum_assignment); default greedy alignment and all other options need only numpy and Pillow]]

Create a virtual environment and install the requirements:

```bash
git clone https://github.com/Xuzhen-Li/qbar.git
cd qbar
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -r requirements.txt
```

Testing was successful on Python 3.13.5 with numpy 2.5.4, Pillow 12.3.0, and scipy 1.18.1. Run the self-check script to verify:

```bash
python3 test_qbar.py
```

## Input files

Q matrix (`.Q`): Contains ancestry proportions.

```text
0.048906 0.126240 0.516154 0.158683 0.000010 0.002808 0.000010 0.147189
0.000010 0.856385 0.015772 0.055593 0.052034 0.000010 0.000010 0.020186
0.000010 0.199419 0.000010 0.770174 0.000010 0.000010 0.000010 0.030357
0.060011 0.000010 0.888786 0.000010 0.013514 0.018525 0.019134 0.000010
0.129499 0.643154 0.000010 0.000010 0.019487 0.091643 0.000010 0.116187
```

Family or ID list (`.fam` or `--ids`): Individual IDs matching the Q matrix rows.

```text
1 1 0 0 0 -9
1-A 1-A 0 0 0 -9
1-W 1-W 0 0 0 -9
10 10 0 0 0 -9
10-A 10-A 0 0 0 -9
```

Groups table: Maps individual IDs to group names.

```text
id	group
1	CG6
1-A	CG2
1-W	W-Ad
10	CG6
```

## Quick start

Run the 2448-sample dataset with K values from 2 to 12. Quote wildcards.

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

Terminal output:

```text
demo/out/panel.png
order	demo/out/order.tsv
```

## Output

Results are saved to the directory specified by `--outdir`.
- `panel.png` and `panel.pdf`: The multi-K summary structure plot.
- `bar_K*.png` and `bar_K*.pdf`: Single structure plot for a specific K value.
- `order.tsv`: Final left-to-right sample order.
- `blocks.tsv`: Start and end sample indices for each group block.
- `align.tsv`: Pearson correlation coefficients used during cross-K alignment.
- `perm_K*.tsv`: Raw column index mapped to aligned ancestry component.
- `args.txt`: Complete command and parameters.

Passing a single .Q file to `--q` produces a single-K plot `bar_K8.png` and `bar_K8.pdf`. No `panel.png` or `panel.pdf` is generated. A single-K run does not write `align.tsv`.

```bash
python3 qbar.py --q demo/2448/ref2448_pruned.8.Q --fam demo/2448/ref2448_pruned.fam --groups demo/2448/groups.tsv --id-col id --group-col group --blocks C-Ad,CG1,CG2,CG3,CG4,CG5,CG6,W-Ad,WEE1,WEE2,WWE1,WWE2 --within iid --color WWE1=#4470b7 --color WEE1=#dc1f26 --color WEE2=#0b5475 --color CG6=#981b1e --color CG4=#f7922c --color CG3=#835ca6 --color CG5=#fbee61 --color WWE2=#f6a3b1 --outdir out/b_singleK8
```

![Single K8](docs/img/b_single_K8.png)

## Common tasks

The example uses the repository's built-in `demo/2448/order.txt`; when using your own list, write one IID per line.

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

```text
out/bar_K8.png
order	out/order.tsv
```

![Custom order](docs/img/f_order_file.png)

Compare within-group sorting: `iid` (default) sorts alphabetically by ID, while `hclust` clusters individuals with similar ancestry profiles.

```bash
python3 qbar.py --q 'demo/2448/ref2448_pruned.[2-6].Q' --fam demo/2448/ref2448_pruned.fam --groups demo/2448/groups.tsv --id-col id --group-col group --blocks C-Ad,CG1,CG2,CG3,CG4,CG5,CG6,W-Ad,WEE1,WEE2,WWE1,WWE2 --within iid --anchor-group WWE1 --outdir out/d_iid
```
![Within iid](docs/img/d_within_iid.png)

```bash
python3 qbar.py --q 'demo/2448/ref2448_pruned.[2-6].Q' --fam demo/2448/ref2448_pruned.fam --groups demo/2448/groups.tsv --id-col id --group-col group --blocks C-Ad,CG1,CG2,CG3,CG4,CG5,CG6,W-Ad,WEE1,WEE2,WWE1,WWE2 --within hclust --anchor-group WWE1 --outdir out/d_hclust
```
![Within hclust](docs/img/d_within_hclust.png)

Apply custom colors to groups and columns.

```bash
python3 qbar.py --q 'demo/2448/ref2448_pruned.[2-6].Q' --fam demo/2448/ref2448_pruned.fam --groups demo/2448/groups.tsv --id-col id --group-col group --blocks C-Ad,CG1,CG2,CG3,CG4,CG5,CG6,W-Ad,WEE1,WEE2,WWE1,WWE2 --within q --anchor-group WWE1 --color WWE1=#4470b7 --color WEE1=#dc1f26 --color CG4=#f7922c --color C3=#2ca02c --outdir out/e_color
```
![Custom colors](docs/img/e_color.png)

Keep the raw ADMIXTURE column order without cross-K alignment.

```bash
python3 qbar.py --q 'demo/2448/ref2448_pruned.[2-6].Q' --fam demo/2448/ref2448_pruned.fam --groups demo/2448/groups.tsv --id-col id --group-col group --blocks C-Ad,CG1,CG2,CG3,CG4,CG5,CG6,W-Ad,WEE1,WEE2,WWE1,WWE2 --within iid --no-align --outdir out/c_noalign
```
![No align](docs/img/c_no_align.png)

## Sorting

You can provide a sample list (one individual ID per line) via the `--order-file` parameter. The generated structure plot will strictly follow this file to order samples from left to right.

If no sample list is provided, you can specify the group order using a comma-separated list via the `--blocks` parameter. Groups present in the group table but omitted in `--blocks` will be appended to the end of the plot in alphabetical order. If neither parameter is provided, all samples are ordered by group name alphabetically by default. For individuals missing group information, their group name is defined by the `--rest-name` parameter (default is NA), and they are placed at the far right of the plot.

Sample sorting logic within groups is controlled by the `--within` parameter:

- `iid`: Sort alphabetically by individual ID. This is the default.
- `q`: Sort in descending order based on the highest ancestry component proportion of the individual within their current group.
- `hclust`: Perform within-group hierarchical clustering. The algorithm uses average linkage and a distance metric of 1 minus the Pearson correlation coefficient, equivalent to scipy's `linkage(method="average", metric="correlation")` ([documentation](https://docs.scipy.org/doc/scipy/reference/generated/scipy.cluster.hierarchy.linkage.html)).
- `input`: Keep the original sample row order from the input Q matrix file.

To apply a different sorting strategy to a specific group, use the `--within-group` parameter (e.g., `--within-group NA=hclust`). This parameter can be declared multiple times.

The `--sort-col 2` parameter forces all groups sorted by `q` to sort in descending order based on the proportion of the 2nd ancestry component. Column numbering starts at 1, corresponding to the aligned ancestry components C1, C2, etc.

## Column alignment

When files with two or more K values are provided, the program automatically aligns columns across K. To keep the original column order for each file, use the `--no-align` parameter.

Alignment modes:
`--align-mode all` is the default. This mode calculates Pearson correlation coefficients using samples from groups specified by `--align-groups`. If `--align-groups` is omitted, all samples are used by default.

`--align-mode core` only keeps individuals whose maximum ancestry component proportion is higher than the `--qmax` threshold (default 0.75) at both adjacent K values. If a group has no individuals meeting this threshold, the single representative individual with the highest ancestry component proportion in that group at the lower K value is selected. The `--align-groups` parameter must be declared when using the core mode.

[[TODO-TEXT: --align-method choices greedy (default, unchanged behaviour) and hungarian; greedy = for aligned column C1..Ck in order, take the unused raw column with the highest Pearson r (ties keep the lower raw index); hungarian = one-to-one assignment of the k old columns to k of the k+1 new columns maximising the summed Pearson r, solved by scipy.optimize.linear_sum_assignment(maximize=True) (scipy already in requirements); in both, the leftover raw column becomes the new last column C(k+1); both use the same people as --align-mode/--align-groups/--qmax select; align.tsv and perm_K*.tsv formats are unchanged; on demo/2448 (K2-12, with and without --anchor-group WWE1, align-mode all and core) both methods give identical column orders, so plots are identical]]

[[TODO-TEXT: --align-method pong, after pong (Behr AA, Liu KZ, Liu-Fang G, Nakka P, Ramachandran S. pong: fast analysis and visualization of latent clusters in population genetic data. Bioinformatics 2016;32(18):2817-2823, doi 10.1093/bioinformatics/btw327; DOI checked against Crossref); qbar's own implementation, not pong's code; similarity = pong's default Jaccard-derived metric from the pong manual eq. 1: 1 - sqrt(sum over N* of (a_i-b_i)^2 / (2|N*|)), N* = people with a_i+b_i>0; for every pair of K+1 columns, the pair is summed into one column, the K old columns are matched one-to-one to the K merged columns by maximum summed similarity (scipy linear_sum_assignment), and the pair with the highest mean similarity wins; the old column matched to the pair is the split parent; of the pair, the one more similar to the parent keeps the parent's position, the other becomes the new last column; needs scipy; with pong, align.tsv columns are K_to, n_mask, pong_sim (similarity of C1..Ck to their match, the parent's value is against the summed pair), split_parent (e.g. C2); the Pearson < 0.5 stderr warning is not printed for pong; on demo/2448 (README quick-start, K2-12) pong gives the same column order as greedy at every K, so the plot is identical; split parents on demo: K3 C2, K4 C3, K5 C3, K6 C2, K7 C3, K8 C2, K9 C1, K10 C1, K11 C6, K12 C4]]

[[TODO-TEXT: --align-method jaccard; qbar's own implementation; per K, each column gets a set of people (only people selected by --align-mode/--align-groups/--qmax): --jaccard-set dominant (default) = people whose highest column is this one (ties to the lower column), --jaccard-set threshold = people with membership >= --jaccard-cut (default 0.5); similarity = Jaccard |A∩B|/|A∪B| (0 if both empty) between each K column and each K+1 column; one-to-one match maximising summed Jaccard with scipy.optimize.linear_sum_assignment, leftover K+1 column becomes the new last column; needs scipy (error `--align-method jaccard 需要 scipy（scipy.optimize）`); align.tsv columns become K_to, n_mask, jaccard; the Pearson < 0.5 stderr warning is not printed for jaccard; contrast: CLUMPAK/CLUMPP align across K by Q-matrix similarity; qbar's jaccard instead uses member-set overlap (qbar's own method); cite Kopelman NM, Mayzel J, Jakobsson M, Rosenberg NA, Mayrose I. Clumpak: a program for identifying clustering modes and packaging population structure inferences across K. Mol Ecol Resour 2015;15(5):1179-1191, doi 10.1111/1755-0998.12387 (checked against Crossref) only as that contrast; with --anchor-group, jaccard may move the anchored component out of C1 (seen on demo/2448 K10-K12); Kong 2024: NOT VERIFIED, no matching paper found (Crossref + web); closest 2024 alignment paper found is Clumppling (Liu X, Kopelman NM, Rosenberg NA. Bioinformatics 2024;40(1):btad751, doi 10.1093/bioinformatics/btad751), not by Kong — do not cite Kong until the exact reference is supplied; on demo/2448 quick-start (K2-12), both dominant and threshold match default at K3-K9; at K10 jaccard keeps the W-Ad component at C1 and the WWE1 component becomes the new C10 (default does the opposite), and that swap of C1/C10 carries through K11 and K12]]

[[TODO-TEXT: --align-report (off by default; default outputs unchanged) writes align_report.tsv and align_report.txt next to align.tsv, only when two or more K are aligned; works with all four --align-method values; one row per column of each K_to (K-1 -> K); TSV columns: K_to, column (aligned C#), raw_column (1-based column in that K's Q file), matched_from (C# at K-1, or new), method, similarity (the method's own measure: Pearson r for greedy/hungarian, pong similarity for pong, Jaccard for jaccard), pearson (Pearson r between the matched columns on the people used for alignment, for reference), low_confidence (yes if similarity < cut, NA for the new column), split_parent, parent_share, top_groups_mean (top 3 groups by mean membership, group:mean), n_dominant (people whose highest column is this one, all people), top_groups_dominant (top 3 groups by that count, group:n); split parent for the new column: pong = the K-1 column matched to pong's split pair; greedy/hungarian/jaccard = the K-1 column with the largest share, share_c = sum_i new_i*prev_ic / sum_i new_i over the people used for alignment; parent_share is that share; low-confidence cut defaults: 0.5 for greedy, hungarian (same as the existing Pearson < 0.5 warning) and jaccard, 0.8 for pong; override with --align-report-low; the txt is English, one block per K step with the same facts; demo/2448 quick-start: no low-confidence rows for greedy, hungarian, pong; jaccard flags 2 (K8 C2 0.496, K11 C5 0.480)]]

The `--anchor-group WWE1` parameter extracts the dominant component of the individual with the highest ancestry component proportion in the specified group (e.g., WWE1) at the lowest K value, and anchors it at the bottom of the structure plot (labeled C1).

Ancestry component plot colors can be specified via parameters, formatted as `--color WWE1=#4470b7` or directly by column number as `--color C3=#112233`. Each ancestry component uses only one color. If the same color is assigned to two different groups, the subsequently conflicting group is automatically assigned an unused new color.

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

[[TODO-TEXT: new common error `--align-method hungarian 需要 scipy（scipy.optimize）`: printed and exit when --align-method hungarian is used without scipy installed; fix = pip install scipy (in requirements.txt) or use the default greedy; likewise `--align-method pong 需要 scipy（scipy.optimize）` for --align-method pong without scipy, same fix; and `--align-method jaccard 需要 scipy（scipy.optimize）` for --align-method jaccard, same fix]]

## Citation

ADMIXTURE mode merging requires CLUMPP (Jakobsson and Rosenberg 2007 *Bioinformatics* 23:1801, [10.1093/bioinformatics/btm233](https://doi.org/10.1093/bioinformatics/btm233)).

Theoretical background of label switching: Alexander, Novembre and Lange 2009 *Genome Res* 19:1655 ([10.1101/gr.094052.109](https://doi.org/10.1101/gr.094052.109)).
