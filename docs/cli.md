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

### `--sites`

Optional TSV. Header: site, latitude, longitude, group, tab-separated. UTF-8, and a BOM is allowed. A site's samples are the people whose group equals that value. Omitted by default, so map_pies.png and map_pies.tsv are not written. --vector does not write a map PDF or SVG. A world file is not read. Nothing is downloaded.

- Default: not set

### `--basemap-image`

PNG stretched to --basemap-bbox. Requires --basemap-bbox and --sites. A missing file is an error. A world file is not read. Nothing is downloaded.

- Default: not set

### `--basemap-bbox`

LON_MIN,LAT_MIN,LON_MAX,LAT_MAX for --basemap-image. A leading minus is accepted. Requires that image. The map uses this box instead of the site extent.

- Default: not set

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

### `--order-mode`

within orders inside groups (default). global-hclust clusters every row as one tree. group-hclust keeps each group contiguous.

- Choices: within, global-hclust, group-hclust
- Default: within

### `--group-order`

Group order for --order-mode group-hclust. input keeps the first-seen order (default). hclust orders groups by the mean Q row.

- Choices: input, hclust
- Default: input

### `--dendrogram`

Dendrogram above the bars. none draws none (default). top is allowed for global-hclust, or for group-hclust with --group-order hclust.

- Choices: none, top
- Default: none

### `--hclust-max-bytes`

Refuse before the distance vector when N*(N-1)/2*8 exceeds this many bytes. 0 means no cap. When omitted, global-hclust, the between-group tree, and --auto-groups hclust use 4294967296, and within-group trees have no cap.

- Default: not set

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

### `--low-confidence-table`

TSV with columns method, cut, precision, recall, n_matches, and split. With --align-report, copy those rows for the active align method onto the end of align_report.txt. Does not change the low-confidence cut.

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

### `--palette`

Bar colours: science, classic, tab10, set1, dark2, or paired. Default science. classic is the previous 20 colours.

- Choices: science, classic, tab10, set1, dark2, paired
- Default: science

### `--color-lock`

off or on. Default off. on keeps each aligned column's colour from the lowest K, unless --color sets that column.

- Choices: off, on
- Default: off

### `--greyscale-preview`

Also write panel_grey.png. Each pixel is round(0.2126*R + 0.7152*G + 0.0722*B) on all three channels. Default off.

- Default: false

### `--vector`

off, pdf, svg, or both. Default off. off keeps the PNG and the raster PDF. pdf writes bar_K*.pdf and panel.pdf as vectors. svg also writes bar_K*.svg and panel.svg, and the PDF stays raster. both writes vector PDFs and SVGs. PNG stays raster. A vector file with more than 200000 bar rectangles is refused and no output file is written.

- Choices: off, pdf, svg, both
- Default: off

### `--html`

Also write panel.html, one offline file. A script draws the bars on a canvas and hover text shows the sample. Default off.

- Default: false

### `--editor`

Also write editor.html and state.json, one offline editor. Default off.

- Default: false

### `--state`

Replay order, colours, names, and column swaps from a state.json file.

- Default: not set

### `--config`

YAML file of settings. Omitted by default. Keys are argparse dest names. Precedence is the command line, then this file, then the defaults. A flag on the command line wins even when it repeats the default.

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

### `--cluster-flow`

Write cluster_flow.tsv, cluster_flow.png, and cluster_flow.pdf. none writes nothing. sankey draws membership weight between aligned columns at consecutive K. Default none.

- Choices: none, sankey
- Default: none

### `--flow-weight`

Edge weight used only with --cluster-flow sankey. share is the destination parent share. jaccard is the member-set Jaccard. Default share.

- Choices: share, jaccard
- Default: share

### `--auto-groups`

Write groups_auto.tsv. none writes nothing (default). major uses the highest column. threshold uses --admix-cut. hclust and kmeans need --auto-g and name groups G1, G2, ... hclust and kmeans can read --pca.

- Choices: none, major, threshold, hclust, kmeans
- Default: none

### `--auto-k`

K of the aligned matrix used for max_q, top_column, and Q clustering. Default: the largest K.

- Default: not set

### `--admix-cut`

Strict cut for --auto-groups threshold. A row is admixed only when its maximum is below this cut. Must be above 0 and at most 1. Default 0.5.

- Default: 0.5

### `--auto-g`

Number of groups for --auto-groups hclust or kmeans. Required for those methods. At least 1, and at most the row count.

- Default: not set

### `--auto-seed`

Seed for --auto-groups kmeans. One numpy Generator draws the 10 restarts. Default 0.

- Default: 0

### `--pca`

PLINK 1.9 eigenvec for --auto-groups hclust or kmeans. No header: FID, IID, then scores. Rows match on IID. Requires --pca-n.

- Default: not set

### `--pca-n`

How many leading score columns to use from --pca. Required with --pca. From 1 up to the number of score columns.

- Default: not set

### `--export`

Comma-separated subset of clumpp and pong. none writes nothing (default). clumpp writes export/clumpp/K<k>.indfile, K<k>.popq, names.txt, and ids.tsv. Indfile column 2 is the same running index as column 1. ids.tsv maps that index to the iid. A tab or a newline in an iid is refused. A space in an iid is kept. pong writes export/pong/K<k>.Q, filemap.txt, and ind2pop.txt. Rows follow the bar order and are not rescaled. With --replicates, each K is the aligned matrix (the major-mode mean when that K has more than one file). An empty group name is refused. A group name is not rewritten.

- Default: none

### `--polygon`

none writes no polygon file (default). simplex writes polygon_K<k>.png and polygon_K<k>.tsv for one aligned K. Each point is the Q-weighted mean of the vertices. C1 is at the top and later vertices go counter-clockwise. Rows match the bar, in bar order, and are not rescaled. K=1 is refused. When K is above 3 the figure says that different Q can share one point. --vector does not write a polygon PDF or SVG.

- Choices: none, simplex
- Default: none

### `--polygon-k`

K used by --polygon simplex. The default is the largest K in the run. A value that is not in the run is an error, and the message names the K values that are.

- Default: not set

## Config file

`--config PATH` reads a YAML mapping. It is omitted by default. PyYAML is imported only when this flag is present. If PyYAML is missing, qbar exits and the message names `pip install "qbar[config]"`.

Precedence is the command line, then the config file, then the defaults from `build_parser`. A flag that is present on the command line wins, including when the value equals the default. A flag that is absent does not replace a value from the file.

Keys are argparse dest names, such as `align_method` and `order_mode`. `align-method` and `--align-method` are accepted and mapped to `align_method`. The key `config` is rejected. The key `state` is allowed and means the same thing as `--state`. The key `export` is a string, the same value as `--export`: `none`, `clumpp`, `pong`, or a comma-separated subset such as `clumpp,pong`. It is not a list. The key `polygon` is `none` or `simplex`, the same string as `--polygon`. The key `polygon_k` is an integer, the same as `--polygon-k`, or null when the flag is omitted. Null means the largest K in the run. Neither key is a file path. `--q` and `--outdir` may be omitted on the command line when the file sets them. A sample id file (`ids`, `fam`, or `ind`) can be set in the file as well. The run still requires one id source.

`on`, `off`, `yes`, and `no` must be quoted when the option expects a string. PyYAML 1.1 reads those words as booleans. A repeated YAML key keeps the last value.

Paths in the file are resolved against the current working directory, the same way as paths on the command line. The directory that contains the config file is not used.

A `store_true` key set to true in the file stays true. The command line cannot turn it off. Those flags have no `--no-` form. The exception is `align`, which has `--align` and `--no-align`. Edit the file to turn the key off.

A float that is not finite is an error and the message names the key. That includes `.nan`, `.inf`, `-.inf`, and the string `NaN` on a float key. The same check applies to a command-line float when `--config` is used, so `config_resolved.json` is not written.

When `--config` is passed and the run finishes, the output directory contains `config_resolved.json`. Keys are sorted, indent is 2, and the file ends with a newline. Each dest is the value the run used. `sources` maps each dest to `cli`, `config`, or `default`. `config_file` is the base name of the YAML file. `config_sha256` is the SHA256 of its bytes. The directory is not stored. File-valued options are base names only. `sites` and `basemap_image` are file-valued options. `basemap_bbox` is the four numbers, not a path. `polygon` and `polygon_k` are not file-valued.

`--state` is applied after that resolution. It replaces sample order and colours. `state_override` records `order` and `colours` when both `--config` and `--state` are used. If the file sets `align_method`, the command line does not pass `--align-method`, and the state names a different method, the run uses the state method. `state_override.align_method` records the config value and the state value. A command-line `--align-method` must still match the state.

`color`, `color_file`, and `order_file` from the file are ignored when `--state` is set. stderr prints one line naming those keys. `state_override` records each one as the config value and `used: state`. File values in that record are base names. Passing `--color`, `--color-file`, or `--order-file` on the command line together with `--state` is still an error.

```yaml
q:
  - k2.Q
  - k3.Q
ids: ids.txt
align_method: hungarian
outdir: out
```
