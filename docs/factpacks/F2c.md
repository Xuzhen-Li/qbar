# F2c. clumpp-largek

Date: 2026-10-23. This note records `--align-method clumpp-largek`. The default method stays `greedy`. `--id-col` stays `analysis_IID`. `--group-col` stays `Dong_Grp`.

## What it returns on this step

`clumpp-largek` pads Q with one zero column, the same padding as `clumpp-full`. It then scores every pair of columns by column G':

```text
G'(a, b) = 1 - ||Q-hat[:, a] - P[:, b]||_2 / sqrt(2C)
```

C is the masked row count. It repeatedly locks the highest remaining pair that reuses no column, until K+1 pairs are locked. Ties take the smaller new-column index, then the smaller old-column index. The P column locked to the zero column is last.

This is the qbar form of CLUMPP LargeKGreedy on one K to K+1 pair. Jakobsson and Rosenberg 2007, Bioinformatics 23(14):1801-1806, DOI 10.1093/bioinformatics/btm233, call that permutation a candidate for the vector that maximises the matrix statistic. The zero padding is the CLUMPAK step. Kopelman et al. 2015, Molecular Ecology Resources 15(5):1179-1191, DOI 10.1111/1755-0998.12387. Clumppling is not this method. Liu, Kopelman, and Rosenberg, DOI 10.1093/bioinformatics/btad751.

There is no stop when K+1 is above 8. The paper presents LargeKGreedy for large K and does not define a hard stop at 8.

## A case that disagrees with clumpp-full

The lock does not claim to maximise matrix G'. The first draw of `numpy.random.default_rng(20261023)`, Q of shape (6, 2) and P of shape (6, 3), both filled with uniform values on [0, 1), and a mask of every row, gives `clumpp-largek` perm `[0, 2, 1]` and `clumpp-full` perm `[0, 1, 2]`. Those lists are 0-based raw columns of P.

A separate invented pair exercises the tie. Both old columns are `[1, 0]`. The three new columns are `[1, 0]`, `[0, 1]`, and `[0, 0]`. More than one pair has column G' equal to 1. The tie rule returns perm `[0, 1, 2]`.

## Scores, report, and replicates

`align.tsv` uses the `gprime` column. Each old column stores column G' against the P column assigned to it. The new column is omitted from that list. The report has no default low-confidence cut, so `low_confidence` is `NA` unless `--align-report-low` is given. `REPORT_LOW` is unchanged for greedy, hungarian, pong, and jaccard. The Pearson < 0.5 stderr warning is not printed. Same-K replicate pairs use Pearson, as for greedy.

## Tests

From the repository root, `python -m unittest test_qbar.py` reported `Ran 138 tests in 4.218s` and `OK`.

The new tests replay the lock from column G' computed in the test, including the tie above. They also require the disagreement perms above. K+1 = 9 returns a permutation of length 9. On that same pair, `clumpp-full` still refuses. The help text contains: `clumpp-largek pads the previous Q with one zero column and repeatedly locks the highest remaining column pair by column G', breaking ties by the smaller new-column index and then the smaller old-column index.`

## Output check

Demo cases against the recorded baseline, with the default method, reported:

```
summary identical=168 pdf-identical=68 identical-after-path-normalisation=24 differ=0 only-in-A=0 only-in-B=0 stderr-identical=0 stderr-differ=12 missing-case=0
result IDENTICAL
```

All 12 stderr rows are the same pair, `sha256 b2a81a4b8571 e3b0c44298fc`. That pair is the older Pillow warning versus empty stderr.

No timing run on this branch.
