# F2d. clumppling-ilp

Date: 2026-10-23. This note records `--align-method clumppling-ilp`. The default method stays `greedy`. `--id-col` stays `analysis_IID`. `--group-col` stays `Dong_Grp`.

## What it returns on this step

`clumppling-ilp` does not pad Q. For masked matrices, with i a column of P (K+1 columns) and j a column of Q (K columns):

```text
C_ij = (1/(2C)) * sum over masked rows (P_li - Q_lj)^2
```

C is the masked row count. The published formula uses the row count N (Liu, Kopelman, and Rosenberg, Bioinformatics, DOI 10.1093/bioinformatics/btad751). qbar uses the same mask as the other align methods, so rows outside the mask are left out of the sum and out of C.

The program minimises sum W_ij C_ij. Each row of W sums to 1. Each column of W sums to at least 1. W is binary. `scipy.optimize.milp` solves it with every variable integer and each variable bounded from 0 to 1. SciPy 1.9.0 added `scipy.optimize.milp` (`https://docs.scipy.org/doc/scipy/release/1.9.0-notes.html`). `pyproject.toml` and `requirements.txt` require `scipy>=1.9.0`. If that import fails, the run stops with `clumppling-ilp needs scipy>=1.9.0 (scipy.optimize.milp)`. A solver status other than 0 stops the run and includes the status and the solver message. There is no stop at K+1 = 8.

Exactly one previous column receives two new columns. That column keeps the child with the smaller C_ij. A tie keeps the smaller new-column index. The other child is last. Every other previous column keeps its single child at that position.

This is not a CLUMPP search. Jakobsson and Rosenberg 2007, DOI 10.1093/bioinformatics/btm233, and Kopelman et al. 2015, DOI 10.1111/1755-0998.12387, are the sources of the other new methods.

## Score column

`align.tsv` uses the `gprime` column. For each old column the value is column G' between that unpadded Q column and the assigned P column, the same column G' as the clumpp methods. The score is not `1 - sqrt(2 * C_ij)`. The new column is omitted from that list, which is the existing leftover convention.

The report has no default low-confidence cut, so `low_confidence` is `NA` unless `--align-report-low` is given. `REPORT_LOW` is unchanged for greedy, hungarian, pong, and jaccard. The Pearson < 0.5 stderr warning is not printed. Same-K replicate pairs use Pearson, as for greedy.

## Tests

From the repository root, `python -m unittest test_qbar.py` reported `Ran 143 tests in 3.671s` and `OK`.

For K of 1, 2, 3, and 4, the test enumerates every surjection from K+1 labels onto K labels, computes the paper cost itself, and requires the milp objective to equal that minimum. The comparison is on the cost. One of those draws drops the first row, so C is the masked count. A separate test builds W by hand: the doubled column keeps the cheaper child, and equal costs keep the smaller index. A mock solver result with status 2 stops the run with the status message. Removing `scipy.optimize.milp` stops the run with the scipy message. The help text contains: `clumppling-ilp assigns each column of the next Q to one column of the previous Q, requires every previous column to receive at least one, minimizes that squared-difference cost, and places the extra column last.`

## Output check

Demo cases against the recorded baseline, with the default method, reported:

```
summary identical=168 pdf-identical=68 identical-after-path-normalisation=24 differ=0 only-in-A=0 only-in-B=0 stderr-identical=0 stderr-differ=12 missing-case=0
result IDENTICAL
```

All 12 stderr rows are the same pair, `sha256 b2a81a4b8571 e3b0c44298fc`. That pair is the older Pillow warning versus empty stderr.

No timing run on this branch.
