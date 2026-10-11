# qbar

读 ADMIXTURE 的 Q，按组排人，把 K 和 K+1 的列对上，画出条形图。

pophelper 在 R 里转表，跨 K 还要另装 CLUMPP。这里一条命令做完。同一个 K 跑了好几次、要从里面挑一次，还是用 CLUMPP（Jakobsson and Rosenberg 2007 *Bioinformatics* 23:1801，[10.1093/bioinformatics/btm233](https://doi.org/10.1093/bioinformatics/btm233)）。

ADMIXTURE 每次都会把组分的左右顺序洗一遍。这里从低 K 接到高 K，用 Pearson 把上一轮的列认出来，新分出来的那一列放在最上面。Alexander, Novembre and Lange 2009 *Genome Res* 19:1655 讲的就是标签切换（[10.1101/gr.094052.109](https://doi.org/10.1101/gr.094052.109)）。

组内如果用 hclust，是平均连锁，距离用 1 减 Pearson，和 scipy 的 `linkage(method="average", metric="correlation")` 一样（[文档](https://docs.scipy.org/doc/scipy/reference/generated/scipy.cluster.hierarchy.linkage.html)）。

Python 3，numpy，Pillow。只有 hclust 需要 scipy。

## 怎么排

`--order-file` 给一份名单，一行一个 IID，图就按这份从左到右。

没有名单就用 `--blocks`，逗号分开。表里有、这里没写的组，按名字接在后面。两个都不给，就按组名排。分组空着的人用 `--rest-name`，默认叫 NA，放在最后。

组内用 `--within`。

- `iid` 按名字。这是默认。
- `q` 按这一组占比最高的那一列，从高到低。
- `hclust` 见上面。
- `input` 保持 Q 原来的行序。

某一组单独改，写 `--within-group NA=hclust`，可以写多次。

`--sort-col 2` 让所有按 `q` 排的组都用第 2 列。列号从 1 开始，按对齐之后的 C1、C2 数。

## 列怎么对

两个以上的 K 会自动对。`--no-align` 就保持每个文件自己的列顺序。

`--align-mode all` 是默认。在 `--align-groups` 点到的人身上做相关。不写 `--align-groups` 就是所有人。

`--align-mode core` 只留这些组里、相邻两个 K 的最大成分都高于 `--qmax` 的人，默认 0.75。某一组一个这样的人都没有，就留这一组在较低 K 上最纯的那一个。core 必须写 `--align-groups`。

`--anchor-group WWE1` 在最低的那个 K 上，把这个组最纯的人的主列放到最下面，记成 C1。

颜色写成 `--color WWE1=#4470b7`，或者 `--color C3=#112233`。一个组分只用一种颜色。两个组给了同一个色，后一个会换成还没用过的。

## 写到哪

都在 `--outdir`。

两个以上的 K 会写出 `panel.png` 和 `panel.pdf`，每个 K 另有 `bar_K2.png` 这种。只有一个 K 时，图就叫 `bar_K8.png`。

`order.tsv` 是从左到右的人。`blocks.tsv` 是每一块从第几人到第几人，`start` 从 1 数。`perm_K8.tsv` 里的 `raw` 是这一列在原来的 Q 里从左数第几列。`align.tsv` 是每一步用了多少人、相关是多少。`args.txt` 是这次的命令。

C1 画在条的最下面。人与人之间不留缝。组与组之间有一条灰线。太窄的组，图上不写名字，人还在 `order.tsv` 里。

`order.tsv` 再拿回来当 `--order-file` 时，认表头里叫 `iid` 的那一列。没有表头，就认每行第一列。

## 2448

`demo/2448/` 里是 2448 人，K 从 2 到 12。人来自 Dong et al. 2023 *Science* 379:892（[10.1126/science.add8655](https://doi.org/10.1126/science.add8655)）。这份 Q 是 seed 43 重跑的。论文 Fig. 1D 用的是他们自己的矩阵，两份不要当成同一份。这里只有成分，没有基因型。各组人数在 `demo/README.md`。

通配符要加引号，不然 shell 会先展开。在 `qbar/` 目录跑：

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

图在 `demo/out/panel.png`。`order.tsv` 有 2448 行，组的顺序和 `--blocks` 一样，组内按名字。

```bash
python3 test_qbar.py
```
