# ST1. Bootstrap support for a column match

Date: 2026-10-23. This note records optional bootstrap support for a column match. `--id-col` stays `analysis_IID`. `--group-col` stays `Dong_Grp`. The procedure is qbar's own. Q values stay fixed.

## What support means

`support` is a resample frequency of the match under fixed Q values. It is not a probability that the cluster is real. It is not a bootstrap of ADMIXTURE. qbar does not resample sites. It resamples individuals (rows).

The analogy is the bootstrap frequency of a recovered group in Felsenstein 1985, Evolution 39(4):783-791, DOI 10.1111/j.1558-5646.1985.tb00420.x. The PDF was not opened. This note gives no equation number. The citation is an analogy only.

## Flags

`--bootstrap` is an integer. The default is 0, which writes no file and does not draw a seed. `--bootstrap-seed` is an integer. The default is 0. It is used only when `--bootstrap` is greater than 0.

A negative `--bootstrap` exits with `--bootstrap must be an integer greater than or equal to 0, got %(n)s`. A negative `--bootstrap-seed` exits with the same form of sentence, and only when `--bootstrap` is greater than 0.

The documented example uses B = 100:

```bash
python3 qbar.py --q sim.2.Q sim.3.Q sim.4.Q sim.5.Q sim.6.Q --ids ids.txt --outdir out --bootstrap 100 --bootstrap-seed 0
```

## Procedure

`bootstrap_support(q_by_k, method, n_boot, seed, mask=None)` in `src/qbar/bootstrap.py` returns one dict per aligned column. The CLI passes the same anchor, align mode, align groups, qmax, and jaccard settings as the full-data run. `mask`, when set, is a boolean vector combined with that align-mode mask. The CLI leaves `mask` unset.

Each replicate draws one index vector with `numpy.random.default_rng(seed).integers(0, n, size=n)`. `n` is the row count. The upper bound is exclusive. That call is the only draw from the generator in the replicate. The same indices are used at every K. The selected align method then runs again from the lowest K upward.

A replicate gives the same match for aligned column c at `K_to` when its raw new-column index equals the full-data raw index. Ties that the matcher breaks differently lower the support.

A replicate whose resampled mask is empty is not the same match. `n_empty_mask` counts those replicates. One empty mask stops that replicate, so the same count is written on every row. Any other qbar error inside a replicate stops the run and names the replicate. A refusal that the full run would also hit, such as `clumpp-full` when K+1 is above 8, is raised by the full-data alignment before the replicates start.

When `--replicates` is on, bootstrap runs on the matrices that were actually aligned, one per K. That is the major-mode mean when that K has two or more files, and the loaded matrix when that K has one file.

Each replicate reruns the align chain from the lowest K upward. The added cost scales with B. The timing below is one greedy measurement, not a recommendation for a slower method.

## File

`match_support.tsv` is written only when `--bootstrap` is greater than 0 and the run aligned at least one K to K+1 step. A single K, or `--no-align`, writes no file.

Columns, in order: `K_to`, `aligned_column`, `raw_column`, `n_boot`, `n_same`, `support`, `seed`, `method`, `n_empty_mask`.

`aligned_column` is `C1`, `C2`, and so on, including the leftover column. `raw_column` is the raw column of the next Q, counted from 1. `support` is `n_same / n_boot`, printed with `%.6f`. There is one row per aligned column at each K step.

## Tests

From the repository root, `python -m unittest test_qbar.py` reported `Ran 156 tests in 5.082s` and `OK`.

A block-diagonal pair where every row in a block is identical has support 1 for the true columns, including the leftover column. A matrix with two identical raw columns has its expected support computed by an independent loop in the test. That loop draws indices with `default_rng(seed).integers(0, n, size=n)` and recomputes the greedy match. It does not call `bootstrap_support` to set the expected value. Seed 0 twice returns the same rows. B = 0 writes no file, including when `--bootstrap-seed` is negative. B = 1 has support 0 or 1. An empty-mask replicate is counted in `n_empty_mask`. A negative `--bootstrap` is an error in English, and `--language zh` raises the Chinese sentence. `--bootstrap 3` writes `match_support.tsv` with the header above. `--id-col` stays `analysis_IID` and `--group-col` stays `Dong_Grp`.

## Output check

Demo cases against the recorded baseline, with the default method and without this flag, reported:

```
summary identical=168 pdf-identical=68 identical-after-path-normalisation=24 differ=0 only-in-A=0 only-in-B=0 stderr-identical=0 stderr-differ=12 missing-case=0
result IDENTICAL
```

All 12 stderr rows are the same pair, `sha256 b2a81a4b8571 e3b0c44298fc`. That pair is the older Pillow warning versus empty stderr. These demo commands do not pass `--bootstrap`.

## Time and memory at N = 10000

Input: `numpy.random.default_rng(20261022)`, `dirichlet(ones(K), size=10000)` for K = 2, 3, 4, 5, 6, saved with `%.6f`, ids `s00000` through `s09999`. Same recipe as S1 and F2e. Command: `qbar.py --q sim.2.Q sim.3.Q sim.4.Q sim.5.Q sim.6.Q --ids ids.txt --outdir OUT`, no `--align-method`, no `--language`, no `--logs`, no `--select-k`, no `--replicates`, and no `--align-compare`, so the method is greedy and replicates are not grouped. `PYTHONHASHSEED=0`. `PYTHONDONTWRITEBYTECODE=1`. Three runs. No separate warmup. Timer: `/usr/bin/time -l` on macOS. Wall seconds are the `real` field. Maximum resident set size is the `maximum resident set size` field, in bytes.

Each run printed four English warnings, the first of which was `Warning: K=2 to 3 has 2 columns with Pearson < 0.5, so these two runs may not be the same solution`. None of the three output directories contained a replicates file, a select_k file, an align_compare file, or `match_support.tsv`.

Machine: `Apple M1 Pro` from `sysctl -n machdep.cpu.brand_string`. `hw.model` = `MacBookPro18,3`. `hw.memsize` = 17179869184. This run used Python 3.9.6. numpy 2.0.2. scipy 1.13.1. Pillow 11.3.0.

| Run | Wall seconds | Max RSS bytes |
| --- | --- | --- |
| 1 | 7.38 | 75857920 |
| 2 | 7.27 | 74203136 |
| 3 | 7.28 | 75563008 |

Median wall 7.28 s. Median of the three maximum resident set sizes 75563008 bytes. Largest of those three sizes 75857920 bytes.

One further run on the same inputs added `--bootstrap 100 --bootstrap-seed 0`. Wall time 7.88 s. Maximum resident set size 86835200 bytes. It printed the same four warnings and wrote `match_support.tsv`.
