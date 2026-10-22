# qbar command line

Generated from `build_parser()`. The option text below is the help string the program ships. It is copied, not rewritten.

读 ADMIXTURE 的 Q，按指定规则排人，跨 K 对齐列，写出结构条形图。

## Notes

排序：--order-file 用你给的名单；否则按 --blocks 的组序分块，组内用 --within。
组内 iid=名字，q=该组占比最高的那一列从高到低，hclust=平均连锁、距离 1−Pearson，input=Q 里的原顺序。
多个 K 默认做 Pearson 贪心对齐，新列放在最上面。--no-align 保持每个 Q 自己的列顺序；若同时给了 --anchor-group，每个 K 仍把该组最纯的人的主列放到 C1。

## Options

### `-h, --help`

show this help message and exit

### `--q`

一个或多个 .Q 或 .q，或带引号的通配符，或一个目录（读取其中的 .Q 和 .q）。只读空白分隔的数字 .Q 或 .q

- Required: yes
- Arguments: +
- Default: not set

### `--q-format`

指定读取的矩阵排版

- Choices: admixture, meanq, qopt
- Default: admixture

### `--fam`

PLINK .fam，IID 在第 2 列，行序与 Q 相同

- Default: not set

### `--ids`

一行一个 IID，行序与 Q 相同。与 --fam 二选一。多出来的字段只保留第一个，并在 stderr 警告

- Default: not set

### `--ind`

EIGENSTRAT 的 .ind，三列，样本号在第 1 列

- Default: not set

### `--groups`

分组表，tsv 或 csv，要有表头

- Default: not set

### `--id-col`

- Default: analysis_IID

### `--group-col`

- Default: Dong_Grp

### `--blocks`

组的从左到右顺序，逗号分隔。组名不能含逗号，否则会被拆开。没写到的组按名字接在后面

- Default: ""

### `--rest-name`

分组为空的人用这个名字。默认 NA

- Default: NA

### `--within`

每一组内部怎么排。默认 iid

- Choices: iid, q, hclust, input
- Default: iid

### `--within-group`

单独改某一组，例如 NA=hclust。可重复

- Default: []

### `--order-file`

一行一个 IID，这就是从左到右的顺序。给了它就不再用 --blocks

- Default: not set

### `--sort-k`

按组分排序时用哪个 K。默认最大的 K

- Default: not set

### `--sort-col`

所有按 q 排序的组都用这一列（从 1 数）。不给就每组用自己占比最高的列

- Default: not set

### `--hclust-k`

hclust 用哪个 K。默认与 --sort-k 相同

- Default: not set

### `--hclust-dist`

hclust 距离。默认 correlation（1−Pearson）

- Choices: correlation, euclidean, braycurtis
- Default: correlation

### `--hclust-linkage`

hclust 连锁法。默认 average。ward 只能配 euclidean

- Choices: average, ward, complete
- Default: average

### `--hclust-pre`

dominant=组内先按每人最高的列分小块（C1、C2…顺序），块内再 hclust。默认 none

- Choices: none, dominant
- Default: none

### `--hclust-olo`

叶序用 scipy optimal_leaf_ordering

- Default: false

### `--align`

- Default: not set

### `--no-align`

- Default: not set

### `--align-mode`

all=掩码内所有人参与对齐，greedy、hungarian、pong、jaccard 用同一批人。Pearson 只用于 greedy 和 hungarian。core=只留相邻两个 K 的 qmax 都严格大于 --qmax 的人；某一组没有人超过时，留下该组在较低 K 上最纯的一个人

- Choices: all, core
- Default: all

### `--align-method`

greedy=按列顺序逐列取 Pearson 最高的未用列（默认）。hungarian=Pearson 总和最大的一一匹配。pong=允许上一 K 的一列拆成两列（Behr 2016），align.tsv 第三列为 pong 相似度并多一列 split_parent。jaccard=按人的集合算 Jaccard 后一一匹配，见 --jaccard-set

- Choices: greedy, hungarian, pong, jaccard
- Default: greedy

### `--jaccard-set`

jaccard 用的集合：dominant=该列是此人最高的列；threshold=此人该列 >= --jaccard-cut。默认 dominant

- Choices: dominant, threshold
- Default: dominant

### `--jaccard-cut`

threshold 集合的阈值。默认 0.5

- Default: 0.5

### `--align-report`

另写 align_report.tsv 和 align_report.txt

- Default: false

### `--align-report-low`

低置信阈值。默认 greedy/hungarian/jaccard 0.5，pong 0.8

- Default: not set

### `--align-groups`

参与对齐的组，逗号分隔。core 模式必填

- Default: ""

### `--qmax`

core 模式的 qmax 阈值。默认 0.75

- Default: 0.75

### `--anchor-group`

对齐时只改最低 K，把这个组最纯的人的主列放到 C1。--no-align 或只有一个 K 时，每个 K 都这样做。

- Default: ""

### `--color`

组名=#rrggbb 或 C3=#rrggbb，在第一个等号处分开。组名不能含等号。可重复

- Default: []

### `--color-file`

两列：名字 #rrggbb

- Default: not set

### `--title`

- Default: ""

### `--width`

条形图宽度，像素

- Default: 2200

### `--bar-height`

每一行条的高度。单个 K 默认 220，多个 K 默认 120

- Default: 0

### `--outdir`

- Required: yes
- Default: not set

### `--provenance`

另写 run.json，记下版本、选项、输入哈希和依赖版本

- Default: false
