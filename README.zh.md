# qbar

[English](README.md)

`qbar` 读取 ADMIXTURE 产生的 Q 矩阵文件，按照预设分组对样本进行排序，并在不同的 K 值之间进行列对齐，最终绘制群体遗传结构条形图。

![Demo panel](docs/img/a_demo_panel.png)

## 安装

本工具需要 Python 3、numpy 与 Pillow。仅当启用 `hclust` 排序时需要 scipy。

[[TODO-TEXT-ZH: same facts as the English Install scipy slot, in Chinese]]

创建虚拟环境并安装依赖：

```bash
git clone https://github.com/Xuzhen-Li/qbar.git
cd qbar
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -r requirements.txt
```

在 Python 3.13.5 下测试通过，numpy 2.5.4、Pillow 12.3.0、scipy 1.18.1。运行脚本自检：

```bash
python3 test_qbar.py
```

## 输入文件

Q 矩阵 (`.Q`)：包含祖先成分比例。

```text
0.048906 0.126240 0.516154 0.158683 0.000010 0.002808 0.000010 0.147189
0.000010 0.856385 0.015772 0.055593 0.052034 0.000010 0.000010 0.020186
0.000010 0.199419 0.000010 0.770174 0.000010 0.000010 0.000010 0.030357
0.060011 0.000010 0.888786 0.000010 0.013514 0.018525 0.019134 0.000010
0.129499 0.643154 0.000010 0.000010 0.019487 0.091643 0.000010 0.116187
```

样本名单 (`.fam` 或 `--ids`)：对应 Q 矩阵行的个体 ID。

```text
1 1 0 0 0 -9
1-A 1-A 0 0 0 -9
1-W 1-W 0 0 0 -9
10 10 0 0 0 -9
10-A 10-A 0 0 0 -9
```

分组表：个体 ID 与群体名称的映射。

```text
id	group
1	CG6
1-A	CG2
1-W	W-Ad
10	CG6
```

## 快速开始

运行 2448 样本数据集，K 值 2 到 12。使用通配符需加引号。

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

终端输出：

```text
demo/out/panel.png
order	demo/out/order.tsv
```

## 输出

结果保存在 `--outdir` 目录。
- `panel.png` 与 `panel.pdf`：跨 K 值的汇总图谱。
- `bar_K*.png` 与 `bar_K*.pdf`：具体 K 值的单张结构图。
- `order.tsv`：自左向右样本排序结果。
- `blocks.tsv`：每个群体区块起始和终止样本编号。
- `align.tsv`：跨 K 值对齐的 Pearson 相关系数。
- `perm_K*.tsv`：原始列序号对应对齐后的祖先成分。
- `args.txt`：运行命令与参数。

只传入一个 `.Q` 文件即为单 K 值运行，生成 `bar_K8.png` 与 `bar_K8.pdf`。不生成 `panel.png` 和 `panel.pdf`。单个 K 的运行不会写入 `align.tsv`。

```bash
python3 qbar.py --q demo/2448/ref2448_pruned.8.Q --fam demo/2448/ref2448_pruned.fam --groups demo/2448/groups.tsv --id-col id --group-col group --blocks C-Ad,CG1,CG2,CG3,CG4,CG5,CG6,W-Ad,WEE1,WEE2,WWE1,WWE2 --within iid --color WWE1=#4470b7 --color WEE1=#dc1f26 --color WEE2=#0b5475 --color CG6=#981b1e --color CG4=#f7922c --color CG3=#835ca6 --color CG5=#fbee61 --color WWE2=#f6a3b1 --outdir out/b_singleK8
```

![Single K8](docs/img/b_single_K8.png)

## 常见用法

示例用仓库自带的 `demo/2448/order.txt`，换成自己的名单时每行写一个 IID。

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

对比组内排序：`iid`（默认）按个体 ID 字母顺序排列，而 `hclust` 会将祖先成分相似的个体聚类在一起。

```bash
python3 qbar.py --q 'demo/2448/ref2448_pruned.[2-6].Q' --fam demo/2448/ref2448_pruned.fam --groups demo/2448/groups.tsv --id-col id --group-col group --blocks C-Ad,CG1,CG2,CG3,CG4,CG5,CG6,W-Ad,WEE1,WEE2,WWE1,WWE2 --within iid --anchor-group WWE1 --outdir out/d_iid
```
![Within iid](docs/img/d_within_iid.png)

```bash
python3 qbar.py --q 'demo/2448/ref2448_pruned.[2-6].Q' --fam demo/2448/ref2448_pruned.fam --groups demo/2448/groups.tsv --id-col id --group-col group --blocks C-Ad,CG1,CG2,CG3,CG4,CG5,CG6,W-Ad,WEE1,WEE2,WWE1,WWE2 --within hclust --anchor-group WWE1 --outdir out/d_hclust
```
![Within hclust](docs/img/d_within_hclust.png)

给群体和祖先列指定颜色。

```bash
python3 qbar.py --q 'demo/2448/ref2448_pruned.[2-6].Q' --fam demo/2448/ref2448_pruned.fam --groups demo/2448/groups.tsv --id-col id --group-col group --blocks C-Ad,CG1,CG2,CG3,CG4,CG5,CG6,W-Ad,WEE1,WEE2,WWE1,WWE2 --within q --anchor-group WWE1 --color WWE1=#4470b7 --color WEE1=#dc1f26 --color CG4=#f7922c --color C3=#2ca02c --outdir out/e_color
```
![Custom colors](docs/img/e_color.png)

关闭对齐，保留原始 Q 矩阵列序。

```bash
python3 qbar.py --q 'demo/2448/ref2448_pruned.[2-6].Q' --fam demo/2448/ref2448_pruned.fam --groups demo/2448/groups.tsv --id-col id --group-col group --blocks C-Ad,CG1,CG2,CG3,CG4,CG5,CG6,W-Ad,WEE1,WEE2,WWE1,WWE2 --within iid --no-align --outdir out/c_noalign
```
![No align](docs/img/c_no_align.png)

## 排序

可通过 `--order-file` 参数提供样本列表（每行一个 ID），生成的结构图将严格遵循该文件排序。

若未提供样本列表，可通过 `--blocks` 参数以逗号分隔的形式指定群体的排列顺序。分组表中未在 `--blocks` 声明的群体将按名称字母顺序追加排列在图像末尾。若均未提供，样本默认按群体名称字母顺序排序。缺失分组信息的个体分组名称由 `--rest-name` 参数定义（默认 NA），放置在图像最右侧。

群体内部样本排序由 `--within` 参数控制：

- `iid`：按个体 ID 字母顺序排列。默认模式。
- `q`：根据最高祖先成分比例降序排列。
- `hclust`：进行组内层次聚类。算法采用平均连锁，距离度量为 1 减去 Pearson 相关系数，等效于 scipy 的 `linkage(method="average", metric="correlation")`（[文档](https://docs.scipy.org/doc/scipy/reference/generated/scipy.cluster.hierarchy.linkage.html)）。
- `input`：保持原输入 Q 矩阵行序。

需对特定群体采用不同排序，使用 `--within-group` 单独指定（例如 `--within-group NA=hclust`），支持多次声明。

`--sort-col 2` 参数强制所有按 `q` 排序的群体依照第 2 列祖先成分比例降序排列。列号从 1 开始计数。

## 列对齐

当输入两个或更多 K 值的文件时，程序自动执行列对齐操作。若需要保持每个输入文件原有的列顺序，使用 `--no-align` 参数。

对齐模式说明：
`--align-mode all` 为默认模式。利用 `--align-groups` 参数指定的群体计算 Pearson 相关系数。若未提供 `--align-groups` 参数，默认利用全体样本计算。

`--align-mode core` 模式仅保留相邻两个 K 值结果中，最大祖先成分比例均高于 `--qmax` 阈值（默认 0.75）的个体。若群体内不存在满足该条件的个体，选取较低 K 值结果中祖先成分比例最高的单一代表个体参与计算。启用 core 模式时必须同时声明 `--align-groups` 参数。

[[TODO-TEXT-ZH: same facts as the English --align-method slot, in Chinese]]

`--anchor-group WWE1` 参数用于在最低 K 值分析结果中，提取指定群体（如 WWE1）内祖先成分比例最高的个体的优势成分，并将其固定排列于图最底层（标记 C1）。

祖先成分的颜色可通过参数指定，格式如 `--color WWE1=#4470b7` 或按列号指定 `--color C3=#112233`。每种祖先成分仅应用单一颜色。若不同群体指定了相同颜色，后续冲突群体自动分配新颜色。

## 常见报错

- `需要 --fam（PLINK .fam）或 --ids（一行一个 IID，顺序与 Q 的行一致）`
  缺少样本名单参数。

- `--fam 和 --ids 只留一个`
  同时提供了两种名单文件，只保留一个。

- `没有匹配到 Q：demo/nothere/*.Q`
  通配符没有匹配到文件，检查路径是否正确。

- `out/ref.4.Q 文件名是 K=4，列数是 3`
  Q 矩阵的列数与文件名里的 K 数字不一致。

- `K=3 的 Q 有 100 行，样本名单有 2448 行`
  Q 矩阵的行数与样本名单数目不匹配。

- `颜色要写成 #rrggbb，收到 blue`
  颜色只能使用十六进制格式输入。

- `锚定组 NOPE 在样本里没有人`
  指定的组名不在当前样本群体表中。

- `要跨 K 对齐，K 必须连续。缺 K=3`
  需要计算的 K 值断层，确保提供的 K 值连续。

- `--sort-col 要在 1 到 3 之间`
  指定用于排序的列号超出了祖先成分数目。

- `hclust 需要 scipy（scipy.cluster.hierarchy）`
  当前环境没有 scipy 库，使用 pip 安装。

[[TODO-TEXT-ZH: same facts as the English common-error hungarian/scipy slot, in Chinese]]

## 引文

合并同一 K 值的多次重复结果需使用 CLUMPP 软件 (Jakobsson and Rosenberg 2007 *Bioinformatics* 23:1801, [10.1093/bioinformatics/btm233](https://doi.org/10.1093/bioinformatics/btm233))。

关于标签切换的理论背景：Alexander, Novembre and Lange 2009 *Genome Res* 19:1655 ([10.1101/gr.094052.109](https://doi.org/10.1101/gr.094052.109))。
