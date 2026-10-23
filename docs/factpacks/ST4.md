# ST4. Parent-share interval, and one parent versus two

Date: 2026-10-23. This note records an optional percentile interval for a parent share, and an optional residual test of one parent column against the runner-up share. `--id-col` stays `analysis_IID`. `--group-col` stays `Dong_Grp`. Both procedures are qbar's own.

`parent_shares` and `split_parent_of` live in `src/qbar/report.py`. The interval and the test live in `src/qbar/parentshare.py`.

## What the interval means

The interval is a percentile interval of row-resample replicates, with the nearest-rank rule as qbar's definition. It is not a probability that a parent column is real.

Sort the B shares of the full-data parent column. Ranks are 1-based. The lower endpoint is the ceil(B * alpha / 2)-th smallest share. The upper endpoint is the ceil(B * (1 - alpha / 2))-th smallest share. For B = 100 and alpha = 0.05 those ranks are 3 and 98. On the shares 0, 1, ..., 99 the endpoints are 2 and 97. If B * alpha / 2 < 1, both endpoints are NA. B * alpha / 2 equal to 1 still has endpoints. For B = 40 and alpha = 0.05 the ranks are 1 and 39.

Efron 1987, Journal of the American Statistical Association 82(397):171-185, DOI 10.1080/01621459.1987.10478410, title "Better Bootstrap Confidence Intervals", is background for a percentile interval. The PDF was not opened. This note gives no equation number. The ranks above are qbar's definition.

## What the test means

`p_one_parent` is qbar's own definition, with the observed statistic included:

```text
p = (1 + count(T* >= T)) / (n_perm + 1)
```

`c` is the original largest-share column. A tie keeps the lower index. `c` is not chosen again inside the permutation. On the alignment mask, `a_hat = sum(w * q_c) / sum(q_c^2)` and `r = w - a_hat * q_c`. One call creates one `numpy.random.default_rng(seed)` and calls `permutation(r)` `n_perm` times. Each permutation sets `w* = a_hat * q_c + r_perm`, recomputes `parent_shares` of `w*`, and sets `T*` to the second-largest share. `T` is the observed second-largest share. Ties count as extreme. The column that holds `T*` can change. Only the fitted column `c` stays fixed.

This asks whether the runner-up share is larger than it is under exchangeable residuals around a one-column linear fit. It can produce `w*` outside [0, 1]. It is not a pong split. It ignores the constraint that a row sums to 1. It is not a likelihood ratio from a published admixture model.

`fraction_outside_unit_interval` is the number of `w*` entries strictly below 0 or strictly above 1, summed over every permutation, divided by `n_perm` times the number of masked rows. Rows outside the mask are not entries. Values equal to 0 or 1 are inside. No tolerance is applied. The fraction is not a p value.

## Flags

`--parent-ci` is off by default. It writes `parent_share_ci.tsv` only when it is on, or when `--parent-test` is on, and the run aligned at least one K to K+1 step. It requires `--bootstrap` greater than 0. It uses `--bootstrap` and `--bootstrap-seed`. If it is on and `--bootstrap` is 0, the run exits with `--parent-ci requires --bootstrap greater than 0. Set --bootstrap.` The Chinese sentence is `--parent-ci 需要设置 --bootstrap。` A negative `--bootstrap` still exits with the bootstrap message, because that check runs first.

`--parent-alpha` is a float. The default is 0.05. A value outside the open interval (0, 1) exits with `--parent-alpha must be greater than 0 and less than 1, got %(alpha)s`, including when `--parent-ci` is off. The default 0.05 does not exit. The Chinese sentence uses the same number and says the value must be greater than 0 and less than 1.

`--parent-test` is off by default. It requires `--perm` greater than 0. It uses `--perm` and `--perm-seed`. If it is on and `--perm` is 0, the run exits with `--parent-test requires --perm greater than 0. Set --perm.` The Chinese sentence is `--parent-test 需要设置 --perm。` The test does not use `--perm-null`. The earlier rule is unchanged: `--perm` greater than 0 still requires `--perm-null`, and that error is raised first. `match_support.tsv` is still written for the chosen null. The parent test draws its own generator.

The interval example:

```bash
python3 qbar.py --q sim.2.Q sim.3.Q sim.4.Q sim.5.Q sim.6.Q --ids ids.txt --outdir out --bootstrap 100 --bootstrap-seed 0 --parent-ci
```

The test example leads with `rows`, because `--perm` greater than 0 still requires a null:

```bash
python3 qbar.py --q sim.2.Q sim.3.Q sim.4.Q sim.5.Q sim.6.Q --ids ids.txt --outdir out --perm 100 --perm-null rows --perm-seed 0 --parent-test
```

## Procedure

`parent_share_ci(shares_boot, alpha=0.05)` returns `ci_low`, `ci_high`, `alpha`, and `n_boot`. NA endpoints are the string NA.

`one_vs_two(q_prev, new_col, mask, n_perm, seed)` fits `c` and permutes the masked residual. One K step creates one `numpy.random.default_rng(seed)` and calls `permutation` on the residual `n_perm` times. The next K step starts again from `--perm-seed`. A masked sum of the new column that is <= 0 does not draw a generator. `sum(q_c^2) <= 0`, a previous matrix with one column, or `n_perm` of 0 also skips the draws and sets `p` to NA.

The parent column is the largest `parent_shares` value on the full-data alignment mask, lower index on a tie. It is not the pong split parent stored on an alignment. The new column is the last aligned column at that K.

The interval uses the row-index vectors already drawn for `--bootstrap`. Those vectors are `numpy.random.default_rng(seed).integers(0, n, size=n)`, one per replicate, including a replicate whose align mask was empty. The parent-share code does not draw a second set and does not align those replicates again. It recomputes `parent_shares` on the full-data aligned matrices and the full-data alignment mask. The parent column stays the full-data column. A replicate whose masked new-column sum is <= 0 contributes 0 to the series.

## File

`parent_share_ci.tsv` is written when `--parent-ci` or `--parent-test` is on and the run aligned at least one K to K+1 step. A single K, or `--no-align`, writes no file. Both flags off writes no file, including when `--bootstrap` or `--perm` is greater than 0. `match_support.tsv` keeps the columns it already had.

Columns, in order: `K_to`, `new_column`, `parent_column`, `share`, `ci_low`, `ci_high`, `alpha`, `n_boot`, `second_column`, `second_share`, `p_one_parent`, `n_perm`, `fraction_outside_unit_interval`.

Floats use `%.6f`. NA is the letters NA. `new_column`, `parent_column`, and `second_column` are aligned labels `C1`, `C2`, and so on. There is one row per K to K+1 step, for the last aligned column.

`second_column` and `second_share` are the observed runner-up. They are filled when the masked new column sums to more than 0, whichever flag is on. When `--parent-ci` is off, `ci_low`, `ci_high`, `alpha`, and `n_boot` are NA. When `--parent-test` is off, `p_one_parent`, `n_perm`, and `fraction_outside_unit_interval` are NA.

A new column whose masked sum is <= 0 has share 0. `parent_column` and `second_column` are NA. The interval and the test are not run. `p_one_parent` is the word `zero_column`. The other interval and test fields are NA. No column was added for that mark. `sum(q_c^2) <= 0` leaves `p_one_parent` and the fraction as NA and still writes `n_perm` when the test was requested. A previous K with one column has no second share, so `p_one_parent` and the fraction are NA and the test is not run.

## Tests

From the repository root, `python -m unittest test_qbar.py` reported `Ran 176 tests in 4.834s` and `OK`.

Previous Q `[[1, 0], [1, 0], [0, 1], [0, 1]]` and new column `(1, 1, 0, 0)` have shares `(1, 0)` by the sums 2 and 0 over total 2. A tie of equal shares keeps the lower index. The residual p equals an independent loop that draws `default_rng(seed).permutation` on the same residual and counts `T* >= T`. That loop does not call `one_vs_two`. `parent_share_ci` on `[0, 1, ..., 99]` with alpha 0.05 returns 2 and 97. Ten shares with alpha 0.05 return NA endpoints. `--parent-ci` without `--bootstrap` is an error in English and in Chinese. `--parent-test` without `--perm` is an error in English and in Chinese. Alpha 0 and alpha 1 are errors. A zero new column writes the header below and the word `zero_column` in `p_one_parent`. `--parent-test` with `--perm` greater than 0 and no `--perm-null` still exits with the message that names `rows` before `column`.

## Output check

Demo cases against the recorded baseline, with the default method and without these flags, reported:

```
summary identical=168 pdf-identical=68 identical-after-path-normalisation=24 differ=0 only-in-A=0 only-in-B=0 stderr-identical=0 stderr-differ=12 missing-case=0
result IDENTICAL
```

All 12 stderr rows are the same pair, `sha256 b2a81a4b8571 e3b0c44298fc`. That pair is the older Pillow warning versus empty stderr. These demo commands do not pass `--parent-ci` or `--parent-test`.

## Time and memory at N = 10000

Input: `numpy.random.default_rng(20261022)`, `dirichlet(ones(K), size=10000)` for K = 2, 3, 4, 5, 6, saved with `%.6f`, ids `s00000` through `s09999`. Same recipe as S1, F2e, ST1, and ST2. Command: `qbar.py --q sim.2.Q sim.3.Q sim.4.Q sim.5.Q sim.6.Q --ids ids.txt --outdir OUT`, no `--align-method`, no `--language`, no `--logs`, no `--select-k`, no `--replicates`, and no `--align-compare`, so the method is greedy and replicates are not grouped. `PYTHONHASHSEED=0`. `PYTHONDONTWRITEBYTECODE=1`. Three runs. No separate warmup. Timer: `/usr/bin/time -l` on macOS. Wall seconds are the `real` field. Maximum resident set size is the `maximum resident set size` field, in bytes.

Each run printed four English warnings, the first of which was `Warning: K=2 to 3 has 2 columns with Pearson < 0.5, so these two runs may not be the same solution`. None of the three output directories contained a replicates file, a select_k file, an align_compare file, `match_support.tsv`, or `parent_share_ci.tsv`.

Machine: `Apple M1 Pro` from `sysctl -n machdep.cpu.brand_string`. `hw.model` = `MacBookPro18,3`. `hw.memsize` = 17179869184. This run used Python 3.9.6. numpy 2.0.2. scipy 1.13.1. Pillow 11.3.0.

| Run | Wall seconds | Max RSS bytes |
| --- | --- | --- |
| 1 | 7.29 | 74137600 |
| 2 | 7.11 | 73793536 |
| 3 | 7.12 | 75890688 |

Median wall 7.12 s. Median of the three maximum resident set sizes 74137600 bytes. Largest of those three sizes 75890688 bytes.

One further run on the same inputs added `--bootstrap 100 --parent-ci`. Wall time 8.46 s. Maximum resident set size 94715904 bytes. It printed the same four warnings and wrote `match_support.tsv` (18 data rows) and `parent_share_ci.tsv` (4 data rows). The interval columns were filled. `p_one_parent`, `n_perm`, and `fraction_outside_unit_interval` were NA. This is 1.34 s above the median default wall. The increment is the 100 full-chain resamples plus the parent-share calculations on those same index vectors. The parent-share step does not align again.

One further run added `--perm 100 --perm-null rows --parent-test`. Wall time 7.82 s. Maximum resident set size 77299712 bytes. It printed the same four warnings and wrote `match_support.tsv` (18 data rows, null `rows`) and `parent_share_ci.tsv` (4 data rows). The interval columns were NA. Each of the four steps had `p_one_parent` 0.009901, which is `(1 + 0) / (100 + 1)`, so none of the 100 residual permutations had a second share at least as large as the observed one. `fraction_outside_unit_interval` was 0.168063, 0.165825, 0.166375, and 0.166561. This is 0.70 s above the median default wall. The command also runs the rows-null match permutation, so 0.70 s is that match test and the residual parent test together. The three default walls span 7.11 s to 7.29 s. Dividing 0.70 s by the four steps gives 0.175 s as the average added time of 100 row shuffles plus 100 residual permutations at one step. That is the full-command difference split evenly across the four steps. It is not a separate clock on the residual loop, and a later step has more columns than the K = 2 step.
