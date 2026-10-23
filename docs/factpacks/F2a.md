# F2a. clumpp-full

Date: 2026-10-23. This note records `--align-method clumpp-full`. The default method stays `greedy`. `--id-col` stays `analysis_IID`. `--group-col` stays `Dong_Grp`.

## What it maximises

qbar's step is one matrix Q at K and one matrix P at K+1. The alignment mask is the same mask the existing methods use (`all` or `core`). Rows outside the mask are excluded from the similarity and from the cost. C is the number of masked rows.

Q-hat is Q with one extra column of zeros on the right, so Q-hat has K+1 columns. The method maximises

```text
G' = 1 - ||Q-hat - P[:, perm]||_F / sqrt(2C)
```

over every permutation of the K+1 columns of P. `perm` lists, for each position in the aligned K+1 order, the raw column of P. Old column c keeps position c. The P column placed on the padded zero column is the new column, and it is last.

Ties: the lexicographically smallest perm tuple. `itertools.permutations` yields that order, and a later permutation replaces the current one only when its G' is strictly larger.

This is a qbar adaptation of CLUMPP FullSearch. Jakobsson and Rosenberg 2007, Bioinformatics 23(14):1801-1806, DOI 10.1093/bioinformatics/btm233. Published FullSearch takes runs that share one K. The zero column is the padding used by CLUMPAK. Kopelman et al. 2015, Molecular Ecology Resources 15(5):1179-1191, DOI 10.1111/1755-0998.12387. The statistic is the PMC form of that paper's G'', with the leading `1 -`. The PDF equation that prints the fraction alone is not used.

The search stops when K+1 is above 8. The English message is `--align-method clumpp-full searches every permutation and stops when K+1 > 8 (here K+1 = 9). Use clumpp-largek or clumppling-ilp.` The Chinese message names the same limit. The number 8 is qbar's own. CLUMPAK's `MAX_K` 8 switches that program to a greedy search. CLUMPP does not define a hard stop at 8. K+1 = 8 still searches.

Clumppling is a different method and is not implemented on this branch. Liu, Kopelman, and Rosenberg, DOI 10.1093/bioinformatics/btad751.

## align.tsv and the report

For this method, `align.tsv` has columns `K_to`, `n_mask`, and `gprime`. The third column is column G' between `Q-hat[:, c]` and the assigned P column, for each old column. Column G' is `1 - ||a - b||_2 / sqrt(2C)`. Values use `%.3f` and are separated by spaces. The new-column score is omitted. That is the existing leftover convention: the score list drops the final missing value. The quantity `1 - sqrt(2 * C_ij)` is not written.

The alignment report calls the similarity `column G'`. `REPORT_LOW` is unchanged: 0.5, 0.5, 0.8, and 0.5 for greedy, hungarian, pong, and jaccard. clumpp-full is not in that dict. Its default low cut is None, so `low_confidence` is `NA` unless `--align-report-low` is given. The split parent uses the same membership-weighted rule as greedy and hungarian. The stderr warning for Pearson < 0.5 stays on greedy and hungarian only.

## Same-K replicates

With `--replicates`, pair similarity for clumpp-full is Pearson, the same column similarity greedy uses, followed by the same one-to-one assignment. It is not matrix G'.

## Tests

From the repository root, `python -m unittest test_qbar.py` reported `Ran 131 tests in 3.595s` and `OK`.

The new tests say the matrices are invented. For K+1 of 2, 3, and 4, including some masks that drop one row, the test enumerates every permutation, computes G' itself, and requires the lex-smallest maximiser. Two identical P columns share one G', and the lex-smallest perm is kept. A planted column swap of a block matrix is recovered as perm `[2, 0, 1]`. K+1 = 9 raises the English message above, and the Chinese message through `align_qs`. K+1 = 8 returns a permutation of length 8. A core mask that drops one person changes the permutation relative to the full mask, and the stored column G' matches `1 - ||diff||_2 / sqrt(2C)` with C = 2. Same-K pair similarity matches an independent Pearson assignment mean, and it matches greedy on that pair.

## Output check

Demo cases against the recorded baseline, with the default method and no new flag, reported:

```
summary identical=168 pdf-identical=68 identical-after-path-normalisation=24 differ=0 only-in-A=0 only-in-B=0 stderr-identical=0 stderr-differ=12 missing-case=0
result IDENTICAL
```

All 12 stderr rows are the same pair, `sha256 b2a81a4b8571 e3b0c44298fc`. That pair is the older Pillow warning versus empty stderr. These demo commands do not select `clumpp-full`.

No timing run on this branch.
