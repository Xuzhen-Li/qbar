# 2448

[English](README.md)

本示例包含 2448 个样本的数据，K 值范围从 2 至 12。样本数据集源自 Dong et al. 2023 *Science* 379:892（[10.1126/science.add8655](https://doi.org/10.1126/science.add8655)）。此处提供的 Q 矩阵文件是指定 seed 为 43 重新运行获得的，原论文 Fig. 1D 展示的是基于原作者另一份矩阵的绘制结果。本示例仅提供群体祖先成分比例矩阵，不包含原始基因型文件。

文件 `ref2448_pruned.fam` 的行序与各个 Q 矩阵文件内部的行序严格保持一致。`groups.tsv` 文件包含两列数据：`id` 与 `group`。

各群体的样本数量具体如下：C-Ad 534，W-Ad 389，CG1 343，CG4 246，WWE1 166，CG5 137，CG6 129，CG3 117，WWE2 112，WEE1 98，CG2 96，WEE2 81。

请在 `qbar/` 目录下运行以下命令：

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

生成的汇总结构图将保存至 `demo/out/panel.png`。生成的 `order.tsv` 文件包含一行表头加 2448 个样本行。
