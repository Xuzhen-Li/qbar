# qbar command line

Generated from `build_parser()`. The option text below is the help string the program ships. It is copied, not rewritten.

Read an ADMIXTURE Q matrix, order people by the rules you set, align columns across K, and write a structure bar plot.

## Notes

Order: --order-file uses the list you give; otherwise groups are blocked in the --blocks order, and --within orders people inside each group.
Inside a group, iid sorts by name, q sorts the column with the highest share in that group from high to low, hclust uses average linkage and distance 1-Pearson, and input keeps the original order in the Q file.
With more than one K, greedy is the default align method. The match is Pearson greedy alignment, and the new column is placed at the top. --no-align keeps each Q file's own column order; if --anchor-group is also set, every K still places that group's purest person's main column at C1.

## Options

### `-h, --help`

show this help message and exit

### `--q`

One or more matrix files, a quoted wildcard, or a directory. The default reads .Q and .q. Which extensions a directory reads is set by --q-format. File contents are whitespace-separated numbers.

- Required: yes
- Arguments: +
- Default: not set

### `--q-format`

Matrix layout to read

- Choices: admixture, meanq, qopt
- Default: admixture

### `--fam`

PLINK .fam, IID in column 2, row order matches Q

- Default: not set

### `--ids`

One IID per line, row order matches Q. Keep only one of --fam, --ids, and --ind. Extra fields keep only the first token, and a warning is written to stderr

- Default: not set

### `--ind`

EIGENSTRAT .ind, three columns, sample id in column 1

- Default: not set

### `--groups`

Group table, tsv or csv, with a header

- Default: not set

### `--id-col`

- Default: analysis_IID

### `--group-col`

- Default: Dong_Grp

### `--blocks`

Left-to-right group order, comma-separated. A group name cannot contain a comma, or it will be split. Groups that are not listed are appended by name

- Default: ""

### `--rest-name`

Name used for a person whose group is empty. Default NA

- Default: NA

### `--within`

How to order people inside each group. Default iid

- Choices: iid, q, hclust, input
- Default: iid

### `--within-group`

Set one group, for example NA=hclust. Repeatable

- Default: []

### `--order-file`

One IID per line. That list is the left-to-right order. When this is set, --blocks is not used

- Default: not set

### `--sort-k`

Which K to use when sorting by ancestry share. Default is the largest K

- Default: not set

### `--sort-col`

Every q-sorted group uses this column (counted from 1). If omitted, each group uses the column where its share is highest

- Default: not set

### `--hclust-k`

Which K hclust uses. Default matches --sort-k

- Default: not set

### `--hclust-dist`

hclust distance. Default correlation (1-Pearson)

- Choices: correlation, euclidean, braycurtis
- Default: correlation

### `--hclust-linkage`

hclust linkage. Default average. ward requires euclidean

- Choices: average, ward, complete
- Default: average

### `--hclust-pre`

dominant first splits each group by each person's highest column (order C1, C2, ...), then runs hclust inside each block. Default none

- Choices: none, dominant
- Default: none

### `--hclust-olo`

Order leaves with scipy optimal_leaf_ordering

- Default: false

### `--align`

- Default: not set

### `--no-align`

- Default: not set

### `--align-mode`

all: everyone in the mask is used for alignment, and greedy, hungarian, pong, jaccard, clumpp-full, clumpp-greedy, clumpp-largek, and clumppling-ilp use the same people. Pearson is used only for greedy and hungarian. core: keep only people whose qmax is strictly greater than --qmax at both adjacent K; if a group has nobody above that cut, keep that group's purest person at the lower K

- Choices: all, core
- Default: all

### `--align-method`

greedy takes the unused column with the highest Pearson value, one old column at a time (default). hungarian is the one-to-one match with the largest sum of Pearson values. pong allows one column from the previous K to split into two (Behr 2016); column 3 of align.tsv is the pong similarity and an extra split_parent column is written. jaccard matches one-to-one on sets of people; see --jaccard-set. clumpp-full pads the previous Q with one zero column and searches every permutation of the next Q to maximize G', keeping the lexicographically smallest permutation on a tie, and stops when K+1 is above 8. clumpp-greedy returns the same permutation as clumpp-full on one K to K+1 pair; the published Greedy differs only with more than two runs at one K. clumpp-largek pads the previous Q with one zero column and repeatedly locks the highest remaining column pair by column G', breaking ties by the smaller new-column index and then the smaller old-column index. clumppling-ilp assigns each column of the next Q to one column of the previous Q, requires every previous column to receive at least one, minimizes that squared-difference cost, and places the extra column last.

- Choices: greedy, hungarian, pong, jaccard, clumpp-full, clumpp-greedy, clumpp-largek, clumppling-ilp
- Default: greedy

### `--jaccard-set`

Set used by jaccard. dominant: this column is the person's highest column. threshold: this person's value in the column is >= --jaccard-cut. Default dominant

- Choices: dominant, threshold
- Default: dominant

### `--jaccard-cut`

Cutoff for the threshold set. Default 0.5

- Default: 0.5

### `--align-report`

Also write align_report.tsv and align_report.txt

- Default: false

### `--align-compare`

Also write align_compare.tsv and align_compare.txt, comparing every available align method with the chosen one. No method is declared better.

- Default: false

### `--align-report-low`

Low-confidence cutoff. Default 0.5 for greedy/hungarian/jaccard, and 0.8 for pong

- Default: not set

### `--align-groups`

Groups that take part in alignment, comma-separated. Required for core mode

- Default: ""

### `--qmax`

qmax cutoff for core mode. Default 0.75

- Default: 0.75

### `--anchor-group`

When aligning, only the lowest K changes: that group's purest person's main column is placed at C1. With --no-align, or when there is only one K, every K does this.

- Default: ""

### `--color`

group=#rrggbb or C3=#rrggbb, split at the first equals sign. A group name cannot contain an equals sign. Repeatable

- Default: []

### `--color-file`

Two columns: name and #rrggbb

- Default: not set

### `--title`

- Default: ""

### `--width`

Bar plot width, in pixels

- Default: 2200

### `--bar-height`

Height of each bar row. Default 220 for a single K, and 120 when there is more than one K

- Default: 0

### `--outdir`

- Required: yes
- Default: not set

### `--provenance`

Also write run.json, recording the version, options, input hashes, and dependency versions

- Default: false

### `--language`

Language for help, errors, and warnings. en or zh

- Choices: en, zh
- Default: en

### `--logs`

ADMIXTURE stdout files, a quoted wildcard, or a directory. A directory reads .out and .log. Default is off.

- Arguments: +
- Default: not set

### `--logs-map`

Two columns, log path and Q path, no header. Each log must be one of the --logs files, and each Q path must exist.

- Default: not set

### `--select-k`

Also write select_k.tsv, select_k.txt, and plots from the CV and log-likelihood table. These are heuristics.

- Default: false

### `--plateau-fraction`

Plateau cut for --select-k. 0.05 is an arbitrary qbar default, not a published constant.

- Default: 0.05

### `--replicates`

Accept several Q files at one K, group them into modes, and align the major-mode mean across K. Off by default.

- Default: false

### `--mode-sim-cut`

Similarity at or above which two replicates are linked into one mode. Required with --replicates. Not calibrated.

- Default: not set

### `--bootstrap`

Resample individuals with replacement this many times and write match_support.tsv. Default 0 writes no file.

- Default: 0

### `--bootstrap-seed`

Seed for --bootstrap. Used only when --bootstrap is greater than 0. Default 0.

- Default: 0

### `--perm`

Permute this many times and append n_perm, n_extreme, p, null, and zero_column to match_support.tsv. Default 0 adds no columns. When this is greater than 0, --perm-null is required.

- Default: 0

### `--perm-seed`

Seed for --perm. Used only when --perm is greater than 0. Default 0.

- Default: 0

### `--perm-null`

Null used when --perm is greater than 0. rows shuffles the K+1 matrix row order and reruns that one match. column shuffles the matched new column across individuals and recomputes its similarity. Required when --perm is greater than 0.

- Choices: rows, column
- Default: not set

### `--parent-ci`

Write parent_share_ci.tsv with a percentile interval for the largest parent share. Off by default. Requires --bootstrap greater than 0. Uses the same row resamples as --bootstrap.

- Default: false

### `--parent-alpha`

Two-sided alpha for --parent-ci. Default 0.05. Must be greater than 0 and less than 1.

- Default: 0.05

### `--parent-test`

Add a residual test of one parent versus two to parent_share_ci.tsv. Off by default. Requires --perm greater than 0. Uses --perm and --perm-seed.

- Default: false
