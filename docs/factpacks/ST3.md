# ST3. Simulation-calibrated low-confidence cuts

Date: 2026-10-23. This note records an optional reader for a precision and recall table, and a scorer for low-confidence flags. This change does not replace 0.5 or 0.8. No calibrated table ships with qbar. qbar does not pick a cut. `--id-col` stays `analysis_IID`. `--group-col` stays `Dong_Grp`.

`REPORT_LOW` stays in `src/qbar/report.py`: greedy 0.5, hungarian 0.5, pong 0.8, jaccard 0.5. The reader and the scorer live in `src/qbar/lowconf.py`. That module does not import Pillow.

## What the table means

The table is a file a later simulation may produce. This change only reads it and copies rows. It does not treat any cut as calibrated. The rule that would replace 0.5 and 0.8 is future work and needs a separate decision. qbar does not ship that rule.

`score_matches(pred_low, truth_wrong)` counts flags against matches that disagree with a planted correspondence. Precision is tp / (tp + fp). Recall is tp / (tp + fn). A zero denominator is None in the returned dict. The report does not call this function. It copies table text, and a cell that already says NA stays the letters NA.

## Flags

`--low-confidence-table` is omitted by default. When it is omitted, qbar does not read a table, does not warn, and does not add text to `align_report.txt`. The low-confidence cut stays `REPORT_LOW`, or the one float from `--align-report-low` when that flag is set. The table never changes either cut.

The header must contain `method`, `cut`, `precision`, `recall`, `n_matches`, and `split`. Extra columns are allowed and are not copied. Column order in the file does not matter. A repeated header name is an error. A missing required column is an error. `cut`, `precision`, and `recall` must be finite numbers, except that `precision` and `recall` may be the token NA. `cut` may not be NA. `n_matches` must be ASCII digits. Cells are copied as stripped text and are not reformatted. Rows stay in file order. There is no comment syntax.

When both `--align-report` and `--low-confidence-table` are set, and the run wrote an alignment report, qbar appends one block at the end of `align_report.txt`. The block begins with a blank line, so the bytes before the block match a run without the table. The title is `Low-confidence table`. The next line is `Copied rows for this align method. These rows do not change the low-confidence cut used above.` The six columns follow, in the order above, for every row whose `method` equals the active `--align-method`. qbar does not rank the rows and does not print a recommended line. The block does not repeat the table path.

If the active method has no rows, qbar writes a warning on stderr and does not append a block. `align_report.txt` stays byte identical to the run without the table. The warning is `Warning: --low-confidence-table has no rows for method greedy. The low-confidence cut is unchanged.` The Chinese sentence is `注意：--low-confidence-table 没有方法 greedy 的行。低置信阈值不变。`

If the table is set without `--align-report`, qbar still reads it, so a bad file is an error, and then warns `Warning: --low-confidence-table is unused without --align-report.` The Chinese sentence is `注意：没有 --align-report 时不使用 --low-confidence-table。` If `--align-report` is set but this run writes no alignment report (one K, or `--no-align`), the warning is `Warning: --low-confidence-table is unused because this run wrote no alignment report.` The Chinese sentence is `注意：这次没有写对齐报告，所以不使用 --low-confidence-table。`

`--language zh` selects the Chinese help and the Chinese warnings. The alignment report text stays English. `--id-col` stays `analysis_IID`. `--group-col` stays `Dong_Grp`.

## Illustrative format

The rows below show the file format only. The numbers are made up. They are not the output of a simulation, and qbar does not use them to choose a cut.

```text
method	cut	precision	recall	n_matches	split
greedy	0.5	0.67	0.50	10	held-out
greedy	0.8	NA	0.25	8	training
```

## Tests

From the repository root, `python -m unittest test_qbar.py` reported `Ran 185 tests in 5.177s` and `OK`.

Ten matches, four of them truly wrong and three flagged, with tp = 2, fp = 1, fn = 2, and tn = 5, give precision 2/3 and recall 1/2. The test computes those fractions from the hand counts. tp + fp = 0 gives precision None. tp + fn = 0 gives recall None. `REPORT_LOW` is greedy 0.5, hungarian 0.5, pong 0.8, jaccard 0.5. A header without `split` is an error. The token `abc` in `precision` is an error. A command with `--align-report` and the table copies the active method's rows, leaves the earlier bytes of `align_report.txt` unchanged, and leaves `low_confidence` unchanged. A table that lacks the active method warns and adds no block.

## Output check

Demo cases against the recorded baseline, with the default method and without this flag, reported:

```text
summary identical=168 pdf-identical=68 identical-after-path-normalisation=24 differ=0 only-in-A=0 only-in-B=0 stderr-identical=0 stderr-differ=12 missing-case=0
result IDENTICAL
```

All 12 stderr rows are the same pair, `sha256 b2a81a4b8571 e3b0c44298fc`. That pair is the older Pillow warning versus empty stderr. These demo commands do not pass `--low-confidence-table`.

## Time and memory at N = 10000

Input: `numpy.random.default_rng(20261022)`, `dirichlet(ones(K), size=10000)` for K = 2, 3, 4, 5, 6, saved with `%.6f`, ids `s00000` through `s09999`. Same recipe as S1, F2e, ST1, ST2, and ST4. Command: `qbar.py --q sim.2.Q sim.3.Q sim.4.Q sim.5.Q sim.6.Q --ids ids.txt --outdir OUT`, no `--align-method`, no `--language`, no `--logs`, no `--select-k`, no `--replicates`, and no `--align-compare`, so the method is greedy and replicates are not grouped. `PYTHONHASHSEED=0`. `PYTHONDONTWRITEBYTECODE=1`. Three runs. No separate warmup. Timer: `/usr/bin/time -l` on macOS. Wall seconds are the `real` field. Maximum resident set size is the `maximum resident set size` field, in bytes.

Each run printed four English warnings, the first of which was `Warning: K=2 to 3 has 2 columns with Pearson < 0.5, so these two runs may not be the same solution`. None of the three output directories contained an align report, a replicates file, a select_k file, an align_compare file, `match_support.tsv`, or `parent_share_ci.tsv`.

Machine: `Apple M1 Pro` from `sysctl -n machdep.cpu.brand_string`. `hw.model` = `MacBookPro18,3`. `hw.memsize` = 17179869184. This run used Python 3.9.6. numpy 2.0.2. scipy 1.13.1. Pillow 11.3.0.

| Run | Wall seconds | Max RSS bytes |
| --- | --- | --- |
| 1 | 7.14 | 74448896 |
| 2 | 7.06 | 76136448 |
| 3 | 7.09 | 74694656 |

Median wall 7.09 s. Median of the three maximum resident set sizes 74694656 bytes. Largest of those three sizes 76136448 bytes.

One further run on the same inputs added `--align-report` and `--low-confidence-table`. The table was a small file of made-up numbers, not a simulation result. Wall time 7.41 s. Maximum resident set size 76382208 bytes. It printed the same four warnings. `align_report.txt` still said `low confidence: similarity < 0.5`, and the copied block was appended after that text. This is 0.32 s above the median default wall. The command also writes the alignment report, so 0.32 s is not a separate clock on reading the table. The three default walls span 7.06 s to 7.14 s.
