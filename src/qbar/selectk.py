"""Heuristics that summarise CV error and log-likelihood by K.

deltaK follows Evanno, Regnaut, and Goudet 2005, Molecular Ecology
14(8):2611-2620, printed page 2614. L(K) is the mean of the numeric
log-likelihood values at that K. s[L(K)] is their sample standard
deviation, with divisor n - 1. The printed expansion is applied to
those means:

    deltaK = |L(K + 1) - 2 L(K) + L(K - 1)| / s[L(K)]

The mean of one absolute second difference is that absolute value.
Using ADMIXTURE log-likelihood is an adaptation of a method described
for STRUCTURE L(K). This module does not import PIL.
"""
from __future__ import annotations

import math
import os

SELECT_K_COLUMNS = (
    "k",
    "n_runs",
    "cv_median",
    "cv_min",
    "cv_max",
    "loglik_mean",
    "loglik_sd",
    "delta_k",
    "min_median_cv",
    "elbow_k",
    "plateau_k",
)

_CAVEAT = (
    "These are heuristics. None of them identifies a true K. "
    "Real populations may not be discrete. Choose K by the biological "
    "question and show several K."
)


def _k_of(row):
    raw = row.get("k", "NA")
    if isinstance(raw, bool):
        return None
    if isinstance(raw, int):
        if raw < 0:
            return None
        return raw
    text = str(raw).strip()
    if text == "NA" or not text.isdigit():
        return None
    return int(text)


def _num(value):
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, str):
        text = value.strip()
        if text == "" or text == "NA":
            return None
        value = text
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def _fmt_float(value):
    if value is None:
        return "NA"
    return str(float(value))


def _fmt_k(value):
    if value is None:
        return "NA"
    return str(int(value))


def _mean(values):
    return sum(values) / float(len(values))


def _median(values):
    ordered = sorted(values)
    count = len(ordered)
    mid = count // 2
    if count % 2:
        return float(ordered[mid])
    return (ordered[mid - 1] + ordered[mid]) / 2.0


def _sample_sd(values):
    """Sample standard deviation. Divisor is n - 1."""
    center = _mean(values)
    total = sum((value - center) ** 2 for value in values)
    return math.sqrt(total / (len(values) - 1))


def _min_median_cv(medians):
    chosen = None
    best = None
    for k in sorted(medians):
        value = medians[k]
        if chosen is None or value < best:
            chosen = k
            best = value
    return chosen


def _elbow_k(medians):
    chosen = None
    best = None
    for k in sorted(medians):
        if (k - 1) not in medians or (k + 1) not in medians:
            continue
        second = medians[k - 1] - 2.0 * medians[k] + medians[k + 1]
        if chosen is None or second > best:
            chosen = k
            best = second
    return chosen


def _plateau_k(medians, fraction):
    """Smallest K whose relative gain stays below ``fraction``.

    The gain is median(K) - median(K - 1). The denominator is the
    absolute value of median(K), because log-likelihoods are negative.
    A larger K with no K - 1 has an undefined gain, so no earlier K is
    returned.
    """
    present = set(medians)
    ratios = {}
    for k in sorted(medians):
        if (k - 1) not in present:
            continue
        scale = abs(medians[k])
        if scale == 0.0:
            continue
        ratios[k] = (medians[k] - medians[k - 1]) / scale
    for k in sorted(medians):
        if k not in ratios or not (ratios[k] < fraction):
            continue
        ok = True
        for later in medians:
            if later <= k:
                continue
            if later not in ratios or not (ratios[later] < fraction):
                ok = False
                break
        if ok:
            return k
    return None


def _delta_k(ks, means, sds, counts):
    """Page 2614 expansion on the per-K means.

    NA at the smallest K, the largest K, and K = 1. NA where K - 1 or
    K + 1 has no mean. NA at a K whose sample standard deviation is 0.
    NA for every K when any K has fewer than 2 numeric log-likelihoods.
    """
    if not ks:
        return {}
    if any(counts[k] < 2 for k in ks):
        return {k: None for k in ks}
    lowest = ks[0]
    highest = ks[-1]
    out = {}
    for k in ks:
        if k == lowest or k == highest or k == 1:
            out[k] = None
            continue
        if (k - 1) not in means or (k + 1) not in means:
            out[k] = None
            continue
        scale = sds[k]
        if scale == 0.0:
            out[k] = None
            continue
        second = abs(means[k + 1] - 2.0 * means[k] + means[k - 1])
        out[k] = second / scale
    return out


def select_k_table(cv_loglik_rows, plateau_fraction=0.05):
    """Summarise F5 rows by K.

    Rows whose ``k`` is ``NA`` are ignored. ``n_runs`` counts the rows
    at that K. CV and log-likelihood summaries use numeric values only.
    ``min_median_cv``, ``elbow_k``, and ``plateau_k`` are repeated on
    every row. Missing values are the string ``NA``. Floats are
    ``str(float(x))``.
    """
    fraction = float(plateau_fraction)
    grouped = {}
    for row in cv_loglik_rows:
        k = _k_of(row)
        if k is None:
            continue
        grouped.setdefault(k, []).append(row)
    ks = sorted(grouped)
    cv_values = {}
    ll_values = {}
    for k in ks:
        cvs = []
        lls = []
        for row in grouped[k]:
            cv = _num(row.get("cv_error", "NA"))
            if cv is not None:
                cvs.append(cv)
            ll = _num(row.get("loglik", "NA"))
            if ll is not None:
                lls.append(ll)
        cv_values[k] = cvs
        ll_values[k] = lls
    cv_median = {k: _median(vs) for k, vs in cv_values.items() if vs}
    cv_min = {k: min(vs) for k, vs in cv_values.items() if vs}
    cv_max = {k: max(vs) for k, vs in cv_values.items() if vs}
    ll_mean = {k: _mean(vs) for k, vs in ll_values.items() if vs}
    ll_median = {k: _median(vs) for k, vs in ll_values.items() if vs}
    ll_sd = {k: _sample_sd(vs) for k, vs in ll_values.items() if len(vs) >= 2}
    counts = {k: len(ll_values[k]) for k in ks}
    deltas = _delta_k(ks, ll_mean, ll_sd, counts)
    min_median = _fmt_k(_min_median_cv(cv_median))
    elbow = _fmt_k(_elbow_k(cv_median))
    plateau = _fmt_k(_plateau_k(ll_median, fraction))
    table = []
    for k in ks:
        table.append({
            "k": str(k),
            "n_runs": str(len(grouped[k])),
            "cv_median": _fmt_float(cv_median.get(k)),
            "cv_min": _fmt_float(cv_min.get(k)),
            "cv_max": _fmt_float(cv_max.get(k)),
            "loglik_mean": _fmt_float(ll_mean.get(k)),
            "loglik_sd": _fmt_float(ll_sd.get(k)),
            "delta_k": _fmt_float(deltas.get(k)),
            "min_median_cv": min_median,
            "elbow_k": elbow,
            "plateau_k": plateau,
        })
    return table


def _has_gap(ks):
    ordered = sorted(ks)
    for left, right in zip(ordered, ordered[1:]):
        if right - left > 1:
            return True
    return False


def _overlap_pairs(table):
    spans = {}
    for row in table:
        if row["cv_min"] == "NA" or row["cv_max"] == "NA":
            continue
        spans[int(row["k"])] = (float(row["cv_min"]), float(row["cv_max"]))
    pairs = []
    for k in sorted(spans):
        if (k + 1) not in spans:
            continue
        left_min, left_max = spans[k]
        right_min, right_max = spans[k + 1]
        if left_min <= right_max and right_min <= left_max:
            pairs.append("%d-%d" % (k, k + 1))
    return pairs


def _delta_paragraph(table):
    sentences = [
        "deltaK was described for STRUCTURE L(K) by Evanno, Regnaut, and Goudet 2005.",
        "L'(K) = L(K) - L(K - 1).",
        "|L''(K)| = |L'(K + 1) - L'(K)|.",
        (
            "deltaK = m(|L''(K)|) / s[L(K)], which expands to "
            "m(|L(K + 1) - 2 L(K) + L(K - 1)|) / s[L(K)]."
        ),
        (
            "qbar sets L(K) to the mean of the numeric ADMIXTURE log-likelihood "
            "values at that K and s[L(K)] to their sample standard deviation."
        ),
        (
            "m(|L''(K)|) is that absolute second difference of the means, "
            "because each K has one mean."
        ),
        "Using ADMIXTURE log-likelihood is an adaptation.",
        "deltaK does not support K = 1.",
        "deltaK is NA at the smallest K and the largest K.",
    ]
    ks = [int(row["k"]) for row in table]
    few = [int(row["k"]) for row in table if row["loglik_sd"] == "NA"]
    if len(few) == 1:
        sentences.append(
            "deltaK is NA for the whole table because K=%d has fewer than 2 "
            "numeric log-likelihood values, so the sample standard deviation "
            "in the formula is not defined for every K." % few[0]
        )
    elif few:
        names = ", ".join("K=%d" % k for k in few)
        sentences.append(
            "deltaK is NA for the whole table because %s have fewer than 2 "
            "numeric log-likelihood values, so the sample standard deviation "
            "in the formula is not defined for every K." % names
        )
    if _has_gap(ks):
        sentences.append(
            "deltaK is NA across a K gap because the difference is undefined "
            "where K-1 or K+1 is missing."
        )
    zeros = []
    for row in table:
        if row["loglik_sd"] == "NA":
            continue
        if float(row["loglik_sd"]) == 0.0:
            zeros.append(int(row["k"]))
    if len(zeros) == 1:
        sentences.append(
            "deltaK is NA at K=%d because the standard deviation of the "
            "log-likelihood at that K is 0." % zeros[0]
        )
    elif zeros:
        names = " and ".join("K=%d" % k for k in zeros)
        sentences.append(
            "deltaK is NA at %s because the standard deviation of the "
            "log-likelihood at those K is 0." % names
        )
    return " ".join(sentences)


def select_k_text(table, plateau_fraction=0.05):
    """Plain-language report. The first line is the required caveat."""
    fraction = str(float(plateau_fraction))
    if table:
        summary = table[0]
    else:
        summary = {"min_median_cv": "NA", "elbow_k": "NA", "plateau_k": "NA"}
    lines = [
        _CAVEAT,
        (
            "min_median_cv = %s. It is the K with the smallest median CV "
            "error. Ties take the smallest K."
        ) % summary["min_median_cv"],
        (
            "elbow_k = %s. It is the interior K with the largest second "
            "difference of the median CV error, d2(K) = cv_median(K-1) - "
            "2 cv_median(K) + cv_median(K+1), among K whose K-1 and K+1 both "
            "have a numeric median. Ties take the smallest K. If no such K "
            "exists, the value is NA."
        ) % summary["elbow_k"],
        (
            "plateau_k = %s. It is the smallest K at which the gain in "
            "median log-likelihood from K-1 to K, divided by the absolute "
            "value of the median log-likelihood at K, is below %s and stays "
            "below it for every larger consecutive K. The absolute value is "
            "used because log-likelihoods are negative. If the series never "
            "does that, the value is NA."
        ) % (summary["plateau_k"], fraction),
        _delta_paragraph(table),
    ]
    pairs = _overlap_pairs(table)
    listed = ", ".join(pairs) if pairs else "none"
    lines.append(
        "Min-max CV ranges that overlap a neighbour K, as pairs: %s." % listed
    )
    return "\n".join(lines) + "\n"


def _write_text(path, text):
    folder = os.path.dirname(os.path.abspath(path))
    if folder:
        os.makedirs(folder, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def write_select_k_tsv(path, table):
    """Write ``select_k.tsv``. Summary K columns are repeated on every row."""
    lines = ["\t".join(SELECT_K_COLUMNS)]
    for row in table:
        lines.append("\t".join(row[name] for name in SELECT_K_COLUMNS))
    _write_text(path, "\n".join(lines) + "\n")


def write_select_k_txt(path, table, plateau_fraction=0.05):
    """Write ``select_k.txt``."""
    _write_text(path, select_k_text(table, plateau_fraction=plateau_fraction))
