# ST2. Permutation p value per match

Date: 2026-10-23. This note records an optional permutation p value for a column match. `--id-col` stays `analysis_IID`. `--group-col` stays `Dong_Grp`. The procedure is qbar's own. No citation is given.

## What the p value means

`p` is qbar's own definition, with the observed statistic included:

```text
p = (1 + count(T* >= T)) / (n_perm + 1)
```

`n_extreme` is `count(T* >= T)`. It does not include the leading 1. Ties count as extreme. The column `null` is always written. A small p is a tail probability under the chosen null. It is not evidence that the index is the true ancestry label.

## Flags

`--perm` is an integer. The default is 0, which adds no columns and does not draw a seed. `--perm-seed` is an integer. The default is 0. It is used only when `--perm` is greater than 0. `--perm-null` is unset by default. When `--perm` is greater than 0 it is required. The choices are `rows` and `column`, and the help lists `rows` first.

A negative `--perm` exits with `--perm must be an integer greater than or equal to 0, got %(n)s`. A negative `--perm-seed` exits with the same form of sentence, and only when `--perm` is greater than 0. If `--perm` is greater than 0 and `--perm-null` is omitted, the run exits with `--perm requires --perm-null when --perm is greater than 0. Choices are rows and column.`

The example uses P = 100 and leads with `rows`:

```bash
python3 qbar.py --q sim.2.Q sim.3.Q sim.4.Q sim.5.Q sim.6.Q --ids ids.txt --outdir out --perm 100 --perm-null rows --perm-seed 0
```

## Null rows

Permute the row order of the whole K+1 matrix with `numpy.random.default_rng(seed).permutation`. Each row stays a composition. Rerun the matcher for that one K step, not the whole chain. The previous matrix is the one already aligned on the full data, so the anchor is already applied. The mask and align mode are the same rules as that step of `align_qs`. T is the unrounded score the matcher returns for that aligned old column: Pearson of the paired columns for greedy and hungarian, `pong_sim` of the two columns for pong, `pong_sim` of the old column and the sum of the two child columns for a pong split parent, Jaccard of the member sets, and column G' of the assigned pair for clumpp-full, clumpp-greedy, clumpp-largek, and clumppling-ilp.

This tests the match index under exchangeability of individuals between the two matrices. It does not test label switching across independent ADMIXTURE runs. A small p means that score is in the upper tail of the shuffled scores. It does not mean the index is the true ancestry label.

An empty mask after a shuffle sets T* to 0 and does not stop the run. Any other error stops the run. Each K step draws its own sequence from `--perm-seed`. Every aligned column at that step is scored from the same sequence.

## Null column

Permute the entries of one matched new column across individuals. Other columns stay put. Recompute that column's similarity to its matched old column. Do not re-solve the assignment. The observed mask stays fixed. The shuffle covers every row of the column, and the similarity is then taken on that mask.

The similarity is Pearson for greedy, hungarian, clumpp-full, clumpp-greedy, clumpp-largek, and clumppling-ilp. It is `pong_sim` for pong, the similarity of the two columns rather than the merged score stored while searching for a split. It is Jaccard for jaccard, with the same member sets, `--jaccard-set`, and `--jaccard-cut` as the matcher. The four clumpp and clumppling methods store column G' in `align.tsv`. This statistic uses Pearson for them, the same column similarity their same-K replicate pairs use.

This breaks the constraint that a row sums to 1, because one column moves and the others do not. It tests whether that column's values, as a vector, line up with the old column above a random reassignment of those values. It does not re-solve the full assignment. It does not test a demographic model. It does not test that a different column would have scored higher.

The leftover column has no matched old column, so `p` and `n_extreme` are `NA` under this null. The null name is still `column`. Under null `rows` the leftover p is `NA`.

## Zero column

An all-zero matched new column, or an all-zero paired old column, sets `zero_column` to `yes`. Otherwise it is `no`. The p value is still computed when T is defined. `n_perm` of 0 returns p as `NA` and does not draw a seed.

## File

`match_support.tsv` is written when `--perm` is greater than 0 and the run aligned at least one K to K+1 step, including when `--bootstrap` is 0. A single K, or `--no-align`, writes no file. When `--perm` is 0, the file stays the bootstrap file: no new columns, and no file when `--bootstrap` is also 0.

Columns appended after `n_empty_mask`, in order: `n_perm`, `n_extreme`, `p`, `null`, `zero_column`.

`p` is printed with `%.6f`, the same width as `support`. `zero_column` is `yes` or `no`. When `--bootstrap` is 0, `n_boot`, `n_same`, `support`, `seed`, and `n_empty_mask` are `NA`. That `seed` column is the bootstrap seed. The permutation seed is not a separate column. `method` stays the align method. When both flags are greater than 0, both column groups are filled, and `seed` is the bootstrap seed.

There is one row per aligned column at each K step, including the leftover column.

## Tests

From the repository root, `python -m unittest test_qbar.py` reported `Ran 167 tests in 4.604s` and `OK`.

A new column copied from old column 0, with a fixed seed, is checked for both nulls. The expected p comes from an independent loop in the test. That loop draws `default_rng(seed).permutation` and counts `T* >= T`. It does not call `permutation_p` to set the expected value. A zero column is checked the same way, and `zero_column` is set. `--perm` greater than 0 without `--perm-null` is an error in English and in Chinese, and the message names `rows` before `column`. A negative `--perm` is an error. `n_perm` of 0 returns p as `NA` and writes no new file. The same seed twice returns the same rows. `--perm 5 --perm-null rows` writes the header `K_to`, `aligned_column`, `raw_column`, `n_boot`, `n_same`, `support`, `seed`, `method`, `n_empty_mask`, `n_perm`, `n_extreme`, `p`, `null`, `zero_column`. `--perm` together with `--bootstrap` fills both column groups. For clumpp-largek, with a mask that drops two rows, the column-null count matches an independent Pearson loop and does not match the column G' count on the same shuffles. `--id-col` stays `analysis_IID` and `--group-col` stays `Dong_Grp`.

## Output check

Demo cases against the recorded baseline, with the default method and without this flag, reported:

```
summary identical=168 pdf-identical=68 identical-after-path-normalisation=24 differ=0 only-in-A=0 only-in-B=0 stderr-identical=0 stderr-differ=12 missing-case=0
result IDENTICAL
```

All 12 stderr rows are the same pair, `sha256 b2a81a4b8571 e3b0c44298fc`. That pair is the older Pillow warning versus empty stderr. These demo commands do not pass `--perm`.

## Time and memory at N = 10000

Input: `numpy.random.default_rng(20261022)`, `dirichlet(ones(K), size=10000)` for K = 2, 3, 4, 5, 6, saved with `%.6f`, ids `s00000` through `s09999`. Same recipe as S1, F2e, and ST1. Command: `qbar.py --q sim.2.Q sim.3.Q sim.4.Q sim.5.Q sim.6.Q --ids ids.txt --outdir OUT`, no `--align-method`, no `--language`, no `--logs`, no `--select-k`, no `--replicates`, and no `--align-compare`, so the method is greedy and replicates are not grouped. `PYTHONHASHSEED=0`. `PYTHONDONTWRITEBYTECODE=1`. Three runs. No separate warmup. Timer: `/usr/bin/time -l` on macOS. Wall seconds are the `real` field. Maximum resident set size is the `maximum resident set size` field, in bytes.

Each run printed four English warnings, the first of which was `Warning: K=2 to 3 has 2 columns with Pearson < 0.5, so these two runs may not be the same solution`. None of the three output directories contained a replicates file, a select_k file, an align_compare file, or `match_support.tsv`.

Machine: `Apple M1 Pro` from `sysctl -n machdep.cpu.brand_string`. `hw.model` = `MacBookPro18,3`. `hw.memsize` = 17179869184. This run used Python 3.9.6. numpy 2.0.2. scipy 1.13.1. Pillow 11.3.0.

| Run | Wall seconds | Max RSS bytes |
| --- | --- | --- |
| 1 | 7.49 | 72155136 |
| 2 | 7.52 | 69812224 |
| 3 | 7.91 | 69468160 |

Median wall 7.52 s. Median of the three maximum resident set sizes 69812224 bytes. Largest of those three sizes 72155136 bytes.

One further run on the same inputs added `--perm 100 --perm-null rows --perm-seed 0`. Wall time 9.67 s. Maximum resident set size 74399744 bytes. It printed the same four warnings and wrote `match_support.tsv` (18 data rows, null `rows`).

One further run added `--perm 100 --perm-null column --perm-seed 0`. Wall time 7.66 s. Maximum resident set size 74858496 bytes. It printed the same four warnings and wrote `match_support.tsv` (18 data rows, null `column`). The four leftover rows have `p` and `n_extreme` equal to `NA`.

The chain has four steps, K = 2 to 3, 3 to 4, 4 to 5, and 5 to 6. The rows run is 2.15 s above the median default wall. Dividing that increment by four steps gives 0.5375 s as the average added time of 100 row shuffles at one step, and 0.005375 s as the average added time of one row shuffle of one step. That is the full-command difference split evenly across the four steps. It is not a separate clock on one step, and a later step matches more columns than the K = 2 step. The column run is 0.14 s above the median. The three default walls span 7.49 s to 7.91 s, so 0.14 s sits inside that spread. The column null recomputes one similarity per permutation and does not rerun the matcher.
