# 2448

2448 人，K 从 2 到 12。样本来自 Dong et al. 2023 *Science* 379:892。Q 是 seed 43 重跑的，论文 Fig. 1D 用的是另一份矩阵。只有祖先成分，没有基因型。

`ref2448_pruned.fam` 的行序和每个 Q 相同。`groups.tsv` 两列，`id` 和 `group`。

人数是 C-Ad 534，W-Ad 389，CG1 343，CG4 246，WWE1 166，CG5 137，CG6 129，CG3 117，WWE2 112，WEE1 98，CG2 96，WEE2 81。

在 `qbar/` 目录：

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

图在 `demo/out/panel.png`。`order.tsv` 应有 2448 行。
