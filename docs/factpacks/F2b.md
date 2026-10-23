# F2b. clumpp-greedy

Date: 2026-10-23. This note records `--align-method clumpp-greedy`. The default method stays `greedy`. `--id-col` stays `analysis_IID`. `--group-col` stays `Dong_Grp`.

## What it returns on this step

On one matrix at K and one matrix at K+1, `clumpp-greedy` uses the same objective, the same search, and the same tie rule as `clumpp-full`. It therefore returns the same permutation. The objective is G' = 1 - ||Q-hat - P[:, perm]||_F / sqrt(2C) after padding Q with one zero column. C is the masked row count. Ties keep the lexicographically smallest perm. The P column on the zero column is last.

`seed` and `repeats` are accepted by the function and ignored. No command-line flag is added for them. They do not change a two-matrix result.

Published CLUMPP Greedy differs only when more than two runs share one K. Jakobsson and Rosenberg 2007, Bioinformatics 23(14):1801-1806, DOI 10.1093/bioinformatics/btm233. That setting is not this K to K+1 pair. The zero padding is the CLUMPAK step. Kopelman et al. 2015, Molecular Ecology Resources 15(5):1179-1191, DOI 10.1111/1755-0998.12387. Clumppling is not this method. Liu, Kopelman, and Rosenberg, DOI 10.1093/bioinformatics/btad751.

The refusal is the same qbar limit as `clumpp-full`, and the message names `clumpp-greedy`. K+1 above 8 stops the run. The number 8 is qbar's own.

## Scores, report, and replicates

`align.tsv` uses the `gprime` column, the same column G' as `clumpp-full`. The new column is omitted from that list. The report has no default low-confidence cut, so `low_confidence` is `NA` unless `--align-report-low` is given. `REPORT_LOW` is unchanged for greedy, hungarian, pong, and jaccard. The Pearson < 0.5 stderr warning is not printed. Same-K replicate pairs use Pearson, as for greedy.

## Tests

From the repository root, `python -m unittest test_qbar.py` reported `Ran 134 tests in 3.916s` and `OK`.

The new tests use invented matrices drawn with `numpy.random.default_rng(20261023)`. For several K+1 of 2, 3, and 4, with and without one masked row, the permutation matches `clumpp-full`. A call that passes a seed and a repeat count returns that same permutation. The help text contains: `clumpp-greedy returns the same permutation as clumpp-full on one K to K+1 pair; the published Greedy differs only with more than two runs at one K.` K+1 = 9 refuses with the message that names `clumpp-greedy`.

## Output check

Demo cases against the recorded baseline, with the default method, reported:

```
summary identical=168 pdf-identical=68 identical-after-path-normalisation=24 differ=0 only-in-A=0 only-in-B=0 stderr-identical=0 stderr-differ=12 missing-case=0
result IDENTICAL
```

All 12 stderr rows are the same pair, `sha256 b2a81a4b8571 e3b0c44298fc`. That pair is the older Pillow warning versus empty stderr.

No timing run on this branch.
