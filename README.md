# qbar

[中文](README.zh.md)

`qbar` reads ADMIXTURE Q matrix files, sorts samples by predefined groups, aligns columns across different K values (number of ancestry components), and plots population genetic structure bar charts.

In R, format conversion usually requires `pophelper`, and cross-K component matching relies on `CLUMPP`. This tool completes the entire workflow from reading matrices to plotting with a single command. Note that merging independent runs of the same K (mode merging) still requires CLUMPP (Jakobsson and Rosenberg 2007 *Bioinformatics* 23:1801, [10.1093/bioinformatics/btm233](https://doi.org/10.1093/bioinformatics/btm233)).

ADMIXTURE runs are subject to label switching, which changes the column order of homologous ancestry components in the matrix. This tool uses a step-by-step matching strategy from low K to high K. It calculates Pearson correlation coefficients to identify the corresponding columns from the previous K and places newly diverged ancestry components at the top of the plot. For the theoretical background of label switching, see Alexander, Novembre and Lange 2009 *Genome Res* 19:1655 ([10.1101/gr.094052.109](https://doi.org/10.1101/gr.094052.109)).

If hierarchical clustering (`hclust`) is used within groups, the algorithm uses average linkage. The distance metric is defined as 1 minus the Pearson correlation coefficient. This logic is equivalent to `linkage(method="average", metric="correlation")` in SciPy (see [documentation](https://docs.scipy.org/doc/scipy/reference/generated/scipy.cluster.hierarchy.linkage.html)).

This tool requires Python 3, numpy, and Pillow. The scipy library is only required when `hclust` sorting is enabled.

## How to sort

You can provide a sample list (one individual ID per line) via the `--order-file` parameter. The generated structure plot will strictly follow this file to order samples from left to right.

If no sample list is provided, you can specify the group order using a comma-separated list via the `--blocks` parameter. Groups present in the group table but omitted in `--blocks` will be appended to the end of the plot in alphabetical order. If neither parameter is provided, all samples are ordered by group name alphabetically by default. For individuals missing group information, their group name is defined by the `--rest-name` parameter (default is NA), and they are placed at the far right of the plot.

Sample sorting logic within groups is controlled by the `--within` parameter:

- `iid`: Sort alphabetically by individual ID. This is the default.
- `q`: Sort in descending order based on the highest ancestry component proportion of the individual within their current group.
- `hclust`: Perform within-group hierarchical clustering (see algorithm details above).
- `input`: Keep the original sample row order from the input Q matrix file.

To apply a different sorting strategy to a specific group, use the `--within-group` parameter (e.g., `--within-group NA=hclust`). This parameter can be declared multiple times.

The `--sort-col 2` parameter forces all groups sorted by `q` to sort in descending order based on the proportion of the 2nd ancestry component. Column numbering starts at 1, corresponding to the aligned ancestry components C1, C2, etc.

## How to align columns

When files with two or more K values are provided, the program automatically aligns columns across K. To keep the original column order for each file, use the `--no-align` parameter.

Alignment modes:
`--align-mode all` is the default. This mode calculates Pearson correlation coefficients using samples from groups specified by `--align-groups`. If `--align-groups` is omitted, all samples are used by default.

`--align-mode core` only keeps individuals whose maximum ancestry component proportion is higher than the `--qmax` threshold (default 0.75) at both adjacent K values. If a group has no individuals meeting this threshold, the single representative individual with the highest ancestry component proportion in that group at the lower K value is selected. The `--align-groups` parameter must be declared when using the core mode.

The `--anchor-group WWE1` parameter extracts the dominant component of the individual with the highest ancestry component proportion in the specified group (e.g., WWE1) at the lowest K value, and anchors it at the bottom of the structure plot (labeled C1).

Ancestry component plot colors can be specified via parameters, formatted as `--color WWE1=#4470b7` or directly by column number as `--color C3=#112233`. Each ancestry component uses only one color. If the same color is assigned to two different groups, the subsequently conflicting group is automatically assigned an unused new color.

## Where to write

All output results are saved to the directory specified by `--outdir`.

When input files contain two or more K values, the program generates a summary plot `panel.png` and a vector format `panel.pdf`. It also outputs a single structure plot for each specific K value (e.g., `bar_K2.png`). For a single K value input, only the corresponding single plot is generated, such as `bar_K8.png`.

The following log files are generated in the directory:
`order.tsv` records the final left-to-right sample order in the plot. `blocks.tsv` records the start and end sample indices for each group block in the plot (`start` coordinates count from 1). The alignment mapping files for each K (e.g., `perm_K8.tsv`) indicate the raw column index in the original Q matrix file corresponding to the aligned ancestry component in the `raw` column. `align.tsv` records the number of samples and corresponding Pearson correlation coefficients used during each cross-K alignment step. `args.txt` saves the complete command and parameters for this run.

For visual layout, the ancestry component labeled C1 is anchored at the very bottom of the bar chart. Samples are packed tightly with no gaps. Different groups are separated by vertical gray lines. If a group block is too narrow, its name label is omitted from the top of the plot, but the individual records remain intact in `order.tsv`.

If the generated `order.tsv` is reused as the `--order-file` parameter, the program automatically identifies the data column named `iid` in the header. If the file has no header, it reads the first data column of each row by default.

## 2448

The `demo/2448/` directory contains a dataset of 2448 samples, with K values ranging from 2 to 12. Samples are from Dong et al. 2023 *Science* 379:892 ([10.1126/science.add8655](https://doi.org/10.1126/science.add8655)). This Q matrix dataset was rerun using seed 43. The Fig. 1D chart in the original paper uses a different matrix provided by the authors; the two should not be confused. The provided data only contains the ancestry component proportion matrix, without genotype files. For specific sample sizes of each group, see `demo/README.md`.

Wildcards must be quoted to prevent the shell from expanding the path prematurely. Run the following command in the `qbar/` directory:

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

The summary plot is saved to `demo/out/panel.png`. The generated `order.tsv` file contains one header line plus 2448 sample rows. Group order matches the `--blocks` parameter, and samples within groups are sorted by individual ID.

```bash
python3 test_qbar.py
```
