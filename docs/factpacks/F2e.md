# F2e. align-compare

Date: 2026-10-23. This note records `--align-compare`. The default method stays `greedy`. The flag is off by default. `--id-col` stays `analysis_IID`. `--group-col` stays `Dong_Grp`.

## What the files contain

`--align-compare` writes `align_compare.tsv` and `align_compare.txt` when there is at least one K to K+1 step. A single K writes neither file.

The TSV columns are exactly `K_to`, `column`, `method`, `matched_from`, `similarity`, `agrees_with_default`. `column` is `C1`, `C2`, and so on, including the new column. `matched_from` is the 1-based raw column of the next Q. `similarity` is that method's own score, printed with three digits, or `NA` when the score is missing. `agrees_with_default` is `yes` or `no`, comparing that raw column with the method selected by `--align-method`.

Each method is run on the chosen method's already aligned previous matrix and the raw next Q, with that step's mask. The chosen method is included. Method order follows the align-method list. `clumpp-full` and `clumpp-greedy` are left out when K+1 is above 8, and the text says so. A method whose scipy symbol does not import is left out, and the text says so. `hungarian`, `pong`, and `jaccard` need `linear_sum_assignment`. `clumppling-ilp` needs `milp`.

The text lists, for each K step, which methods share the chosen mapping and which do not, with the similarity values. It begins `No method is declared better.` It has no winner line. The chosen alignment, including `align.tsv` and the permutation files, is unchanged.

The four new methods are the ones in Jakobsson and Rosenberg 2007 (DOI 10.1093/bioinformatics/btm233), Kopelman et al. 2015 (DOI 10.1111/1755-0998.12387), and Liu, Kopelman, and Rosenberg (DOI 10.1093/bioinformatics/btad751). This report does not rank them.

## Tests

From the repository root, `python -m unittest test_qbar.py` reported `Ran 146 tests in 3.867s` and `OK`.

The existing greedy versus hungarian fixture is reloaded from the saved Q files. The test recomputes the greedy permutation and the hungarian permutation by brute force. Where those raw columns differ, the hungarian row has `agrees_with_default` `no`. A run without the flag does not write the two files, and `align.tsv` and `perm_K3.tsv` match the run that sets the flag. K+1 = 9 names the two skipped permutation searches. Removing `milp` names that skip. The English help is: `Also write align_compare.tsv and align_compare.txt, comparing every available align method with the chosen one. No method is declared better.`

## Output check

Demo cases against the recorded baseline, with the default method and without this flag, reported:

```
summary identical=168 pdf-identical=68 identical-after-path-normalisation=24 differ=0 only-in-A=0 only-in-B=0 stderr-identical=0 stderr-differ=12 missing-case=0
result IDENTICAL
```

All 12 stderr rows are the same pair, `sha256 b2a81a4b8571 e3b0c44298fc`. That pair is the older Pillow warning versus empty stderr.

## Time and memory at N = 10000

Input: `numpy.random.default_rng(20261022)`, `dirichlet(ones(K), size=10000)` for K = 2, 3, 4, 5, 6, saved with `%.6f`, ids `s00000` through `s09999`. Command: `qbar.py --q sim.2.Q sim.3.Q sim.4.Q sim.5.Q sim.6.Q --ids ids.txt --outdir OUT`, no `--align-method`, no `--language`, no `--logs`, no `--select-k`, no `--replicates`, and no `--align-compare`. `PYTHONHASHSEED=0`. `PYTHONDONTWRITEBYTECODE=1`. Three runs. No separate warmup. Timer: `/usr/bin/time -l` on macOS. Wall seconds are the `real` field. Maximum resident set size is the `maximum resident set size` field, in bytes.

Each run printed four English warnings, the first of which was `Warning: K=2 to 3 has 2 columns with Pearson < 0.5, so these two runs may not be the same solution`. None of the three output directories contained a replicates file, a select_k file, or an align_compare file.

Machine: `Apple M1 Pro` from `sysctl -n machdep.cpu.brand_string`. `hw.model` = `MacBookPro18,3`. `hw.memsize` = 17179869184. This run used Python 3.9.6. numpy 2.0.2. scipy 1.13.1. Pillow 11.3.0.

| Run | Wall seconds | Max RSS bytes |
| --- | --- | --- |
| 1 | 7.36 | 69730304 |
| 2 | 7.17 | 76644352 |
| 3 | 7.27 | 75431936 |

Median wall 7.27 s. Median of the three maximum resident set sizes 75431936 bytes. Largest of those three sizes 76644352 bytes.

One further run on the same inputs added only `--align-compare`. Wall time 8.18 s. Maximum resident set size 110116864 bytes. It printed the same four warnings and wrote `align_compare.tsv` and `align_compare.txt`.
