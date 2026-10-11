# 2448

[中文](README.zh.md)

This demo contains data for 2448 samples, with K values ranging from 2 to 12. The sample dataset is from Dong et al. 2023 *Science* 379:892. The Q matrix files provided here were obtained by rerunning with seed 43. Fig. 1D in the original paper is based on a different matrix from the authors. This demo only provides the population ancestry component proportion matrix and does not include the raw genotype files.

The row order of the `ref2448_pruned.fam` file is strictly identical to the row order inside each Q matrix file. The `groups.tsv` file contains two columns: `id` and `group`.

The sample counts for each group are as follows: C-Ad 534, W-Ad 389, CG1 343, CG4 246, WWE1 166, CG5 137, CG6 129, CG3 117, WWE2 112, WEE1 98, CG2 96, WEE2 81.

Run the following command in the `qbar/` directory:

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

The generated summary structure plot is saved to `demo/out/panel.png`. The generated `order.tsv` file contains one header line plus 2448 sample rows.
