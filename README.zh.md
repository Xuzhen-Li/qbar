# qbar

[English](README.md)

`qbar` 用于读取 ADMIXTURE 产生的 Q 矩阵文件，按照预设分组对样本进行排序，并在不同的 K 值（祖先成分数量）之间进行跨 K 值的列对齐，最终绘制群体遗传结构条形图。

在 R 语言环境中通常需要使用 `pophelper` 转换格式，并依赖 `CLUMPP` 解决跨 K 值的成分匹配问题。本工具通过单条命令即可完成从矩阵读取到绘图的全流程。需要注意的是，若要合并同一 K 值的多次重复运行结果（mode merging），仍需使用 CLUMPP 软件（Jakobsson and Rosenberg 2007 *Bioinformatics* 23:1801，[10.1093/bioinformatics/btm233](https://doi.org/10.1093/bioinformatics/btm233)）。

ADMIXTURE 在每次运行时会出现标签切换现象（label switching），导致同源祖先成分在矩阵中的列序发生改变。本工具采用从低 K 值到高 K 值的逐步匹配策略，利用 Pearson 相关系数识别前一轮分析中的对应列，并将新分化出的祖先成分排列于图像的最上方。关于标签切换的理论背景，可参考 Alexander, Novembre and Lange 2009 *Genome Res* 19:1655（[10.1101/gr.094052.109](https://doi.org/10.1101/gr.094052.109)）。

在各群体内部若使用层次聚类（`hclust`），算法采用平均连锁（average linkage），距离度量定义为 1 减去 Pearson 相关系数。该逻辑等效于 SciPy 库中的 `linkage(method="average", metric="correlation")`（详见[文档](https://docs.scipy.org/doc/scipy/reference/generated/scipy.cluster.hierarchy.linkage.html)）。

本工具依赖 Python 3、numpy 与 Pillow 库。仅当启用 `hclust` 排序时额外依赖 scipy 库。

## 怎么排

可通过 `--order-file` 参数提供一份样本列表（每行包含一个个体 ID），生成的结构图将严格遵循该文件自左向右排列样本。

若未提供样本列表，则可通过 `--blocks` 参数以逗号分隔的形式指定群体的排列顺序。若分组表中存在未在 `--blocks` 参数中声明的群体，这些群体将按名称的字母顺序追加排列在图像末尾。若上述两个参数均未提供，全体样本将默认按群体名称的字母顺序进行排序。对于缺失分组信息的个体，其分组名称由 `--rest-name` 参数定义（默认值为 NA），这些个体将被统一放置在图像的最右侧。

群体内部的样本排序逻辑由 `--within` 参数控制：

- `iid`：按个体 ID 的字母顺序排列。此为默认模式。
- `q`：根据该个体在当前所属群体中占比最高的祖先成分比例，由高到低进行降序排列。
- `hclust`：进行组内层次聚类（算法细节详见上文）。
- `input`：保持原输入 Q 矩阵文件中的样本行序。

若需对特定群体采用不同的组内排序策略，可使用 `--within-group` 参数单独指定（例如 `--within-group NA=hclust`），该参数支持多次声明。

参数 `--sort-col 2` 可用于强制指定所有按 `q` 模式排序的群体均依照第 2 列的祖先成分比例进行降序排列。此处的列号从 1 开始计数，对应列对齐处理后的 C1、C2 等祖先成分。

## 列怎么对

当输入两个或更多 K 值的文件时，程序会自动执行跨 K 值的列对齐操作。若需要保持每个输入文件原有的列顺序，请使用 `--no-align` 参数。

对齐模式说明：
`--align-mode all` 为默认模式。该模式将利用 `--align-groups` 参数指定的群体样本计算 Pearson 相关系数。若未提供 `--align-groups` 参数，则默认利用全体样本进行计算。

`--align-mode core` 模式将仅保留在相邻两个 K 值的分析结果中，其最大祖先成分比例均高于 `--qmax` 阈值（默认值为 0.75）的个体。若某群体内不存在满足该阈值条件的个体，则选取该群体在较低 K 值结果中祖先成分比例最高的单一代表个体参与计算。启用 core 模式时必须同时声明 `--align-groups` 参数。

`--anchor-group WWE1` 参数用于在最低 K 值的分析结果中，提取指定群体（如 WWE1）内祖先成分比例最高的个体的优势成分，并将其固定排列于结构图的最底层（标记为 C1）。

祖先成分的绘图颜色可通过参数指定，格式如 `--color WWE1=#4470b7` 或直接按列号指定如 `--color C3=#112233`。每一种祖先成分仅应用单一颜色。若为两个不同的群体指定了相同的颜色，后续遇到颜色冲突的群体将被自动分配一种尚未被使用的新颜色。

## 写到哪

所有的分析输出结果均将保存至 `--outdir` 参数指定的目录下。

当输入文件包含两个或以上的 K 值时，程序将生成汇总图谱 `panel.png` 与矢量格式的 `panel.pdf` 文件，同时为每个具体的 K 值输出单张结构图（例如 `bar_K2.png`）。当仅输入单个 K 值时，只会生成对应的单张图谱，如 `bar_K8.png`。

目录下同时生成以下记录文件：
`order.tsv` 记录了图谱自左向右所有样本的最终排序结果。`blocks.tsv` 记录了图像中每个群体区块起始和终止的样本编号（`start` 坐标从 1 开始计数）。各 K 值的对齐映射文件（如 `perm_K8.tsv`）中的 `raw` 列指示了对齐后的祖先成分对应于原始 Q 矩阵文件中自左向右的列序号。`align.tsv` 记录了每步跨 K 值对齐过程中所使用的样本数量以及对应的 Pearson 相关系数。`args.txt` 保存了本次执行的完整命令与参数。

在可视化排版上，标记为 C1 的祖先成分将固定绘制于条形图的最底层。样本之间紧密排列不留空隙，不同群体之间使用灰色竖线作为边界分隔。若某个群体在图像中的宽度过窄，图谱顶部将省略该群体的名称标注，但对应的个体信息仍会完整记录在 `order.tsv` 文件中。

若将生成的 `order.tsv` 再次作为 `--order-file` 参数输入，程序将自动识别表头中名为 `iid` 的数据列。若输入文件不包含表头，则默认读取每行的第一列数据。

## 2448

`demo/2448/` 目录下包含了 2448 个样本的数据集，包含从 K=2 到 K=12 的分析结果。样本源自 Dong et al. 2023 *Science* 379:892（[10.1126/science.add8655](https://doi.org/10.1126/science.add8655)）。该 Q 矩阵数据集是使用 seed 43 重新运行生成的，原论文 Fig. 1D 图表使用的是原作者提供的另一份分析矩阵，二者不应混同。提供的数据中仅包含祖先成分比例矩阵，不含基因型文件。各群体具体的样本量分布参见 `demo/README.md`。

在使用通配符匹配文件时必须添加引号，以防止 shell 环境提前展开路径。请在 `qbar/` 目录下执行以下命令：

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

生成的汇总图谱将保存至 `demo/out/panel.png` 路径下。生成的 `order.tsv` 文件包含一行表头加 2448 个样本行，群体的排序与 `--blocks` 参数声明的顺序一致，各群体内部的样本按照个体 ID 排序。

```bash
python3 test_qbar.py
```
