# Choosing an alignment method

`--align-method` accepts `greedy` (the default), `hungarian`, `pong`, or `jaccard`. Matching runs from one K to the next. The two Q matrices must have column counts that differ by 1. Every method uses the same people. With `--align-mode all` (the default) that is everyone, or only the groups listed in `--align-groups` when that option is set. With `--align-mode core`, a person is kept when their maximum value is strictly above `--qmax` (default 0.75) at both K. If a listed group has nobody above that cut, the purest person in that group at the lower K is kept.

`greedy` walks the old columns in order. Each one takes the unused new column with the highest Pearson correlation. An equal correlation keeps the lower new-column index. The new column left over is placed last. If a matched correlation is below 0.5, qbar prints a warning on stderr. This method does not import scipy.

`hungarian` uses that same Pearson matrix. `scipy.optimize.linear_sum_assignment` (`maximize=True`) picks a one-to-one assignment that maximizes the sum. The leftover new column goes last. A matched correlation below 0.5 prints the same warning. This method imports scipy.

`pong` scores two columns as `1 - sqrt(sum((a - b)^2) / (2N))` for people with `a + b > 0`. If no person meets that test, the score is 0. Each pair of new columns is summed into one column and matched to the old columns by the maximum sum of scores. The pair with the highest mean score is kept. The old column matched to that pair is the split parent. Of the two new columns, the one with the greater or equal score keeps the parent's place (the lower raw index when the scores are equal), and the other goes last. `align.tsv` then includes `pong_sim` and `split_parent`. This method imports scipy. It does not print the Pearson 0.5 warning.

`jaccard` matches sets of people. `--jaccard-set dominant` (the default) is the people for whom that column is the highest value, and a tie keeps the lower column index. `threshold` is the people whose value is at least `--jaccard-cut` (default 0.5). The score is the number of shared people divided by the number of people in either set, or 0 when that union is empty. The assignment maximizes the sum of the scores, and the leftover column goes last. This method imports scipy.

`greedy` is the default, and it is the method that runs without scipy. Use `hungarian` when the assignment should maximize the summed Pearson correlation instead of taking columns in order. Use `pong` when one old column should be allowed to split into two new columns. Use `jaccard` when the match should follow which people belong to a column rather than the numeric values in the column.

Speed and agreement across methods are [NEEDS-RUN: benchmark P3].
