"""Read ADMIXTURE stdout for CV error and log-likelihood.

``parse_admixture_log`` returns one row for a file that contains
``ADMIXTURE Version``, or one row per CV line when every non-blank line
is a CV line. Numeric tokens stay as printed. Missing fields are the
string ``NA``.
"""
from __future__ import annotations

import glob
import os
import re
import sys

from .messages import text as _msg

_COLUMNS = (
    "file",
    "k",
    "seed",
    "cv_error",
    "loglik",
    "iterations",
    "converged",
    "warnings",
)

# Integers and plain or scientific floats, kept as the printed token.
_NUM = r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?"
_CV = re.compile(r"^\s*CV error \(K=(\d+)\): (" + _NUM + r")\s*$")
_SEED = re.compile(r"^Random seed: (\d+)$")
_FOLDS = re.compile(r"^Cross-validation will be performed\.  Folds=(\d+)\.$")
_THREADS = re.compile(r"^Parallel execution requested\.  Will use (\d+) threads\.$")
_DELTA = re.compile(
    r"^Point estimation will terminate when objective function delta < (" + _NUM + r")$"
)
_SIZE = re.compile(r"^Size of G: (\d+)x(\d+)$")
_EM = re.compile(
    r"^(\d+) \(EM\) \tElapsed: (" + _NUM + r")\tLoglikelihood: ("
    + _NUM + r")\t\(delta\): (" + _NUM + r")$"
)
_QN = re.compile(
    r"^(\d+) \(QN/Block\) \tElapsed: (" + _NUM + r")\tLoglikelihood: ("
    + _NUM + r")\t\(delta\): (" + _NUM + r")$"
)
_INITIAL = re.compile(r"^Initial loglikelihood: (" + _NUM + r")$")
_CONVERGED = re.compile(
    r"^Converged in (\d+) iterations \((" + _NUM + r") sec\)$"
)
_LOGLIK = re.compile(r"^Loglikelihood: (" + _NUM + r")$")
_SUMMARY = re.compile(r"^Summary:[ ]*$")
_FST_HEADER = re.compile(r"^Fst divergences between estimated populations:[ ]*$")
_FST_TOKEN = r"(?:Pop\d+|[+-]?(?:\d+(?:\.\d*)?|\.\d+))"
_FST_ROW = re.compile(r"^(?:" + _FST_TOKEN + r")?(?:\t(?:" + _FST_TOKEN + r")?)*$")
_PARTIAL_ITER = re.compile(r"^\d+ \((?:EM|QN/Block)\)")

_FIXED = {
    "Point estimation method: Block relaxation algorithm",
    "Convergence acceleration algorithm: QuasiNewton, 3 secant conditions",
    "Estimation of standard errors disabled; will compute point estimates only.",
    "Performing five EM steps to prime main algorithm",
    "Starting main algorithm",
    "Writing output files.",
}


def _empty_row(path):
    row = {name: "NA" for name in _COLUMNS}
    row["file"] = path
    return row


def _die(path, line, language):
    raise SystemExit(_msg("log_format", language, path=path, line=line))


def _banner_line(line):
    stripped = line.rstrip(" \t")
    return stripped.startswith("****") and stripped.endswith("****") and len(stripped) >= 8


def _partial_iter(line):
    if _PARTIAL_ITER.match(line) is None:
        return False
    return _EM.match(line) is None and _QN.match(line) is None


def _classify(line):
    """Return (kind, payload) for one allowed line, or ('bad', None)."""
    if line == "":
        return "blank", None
    if _banner_line(line):
        return "banner", None
    matched = _CV.match(line)
    if matched:
        return "cv", (matched.group(1), matched.group(2))
    matched = _SEED.match(line)
    if matched:
        return "seed", matched.group(1)
    if _FOLDS.match(line) or _THREADS.match(line) or _DELTA.match(line) or _SIZE.match(line):
        return "meta", None
    if line in _FIXED:
        return "fixed", None
    if _EM.match(line) or _QN.match(line):
        return "iter", None
    if _INITIAL.match(line):
        return "initial", None
    if _SUMMARY.match(line):
        return "summary", None
    matched = _CONVERGED.match(line)
    if matched:
        return "converged", matched.group(1)
    if line.startswith("Loglikelihood:") and "Elapsed:" not in line:
        matched = _LOGLIK.match(line)
        if matched:
            return "loglik", matched.group(1)
        return "bad", None
    if _FST_HEADER.match(line):
        return "fst", None
    if line != "" and _FST_ROW.match(line) and _FST_ROW.match(line).group(0) == line:
        if line.strip("\t") == "":
            return "bad", None
        return "fst", None
    return "bad", None


def _warn(path, language, no_cv, truncated):
    parts = []
    if no_cv:
        parts.append(_msg("log_no_cv", language, path=path))
    if truncated:
        parts.append(_msg("log_truncated", language, path=path))
    for part in parts:
        print(part, file=sys.stderr)
    if not parts:
        return "NA"
    return "; ".join(parts)


def _parse_cv_only(path, lines, language):
    rows = []
    for line in lines:
        if line == "":
            continue
        kind, payload = _classify(line)
        if kind != "cv":
            _die(path, line, language)
        row = _empty_row(path)
        row["k"] = payload[0]
        row["cv_error"] = payload[1]
        rows.append(row)
    if not rows:
        _die(path, lines[0] if lines else "", language)
    return rows


def _parse_banner(path, lines, ends_nl, language):
    row = _empty_row(path)
    seen = {"cv": False, "seed": False, "loglik": False, "converged": False}
    truncated = False
    last_index = len(lines) - 1
    for index, line in enumerate(lines):
        if line == "":
            continue
        kind, payload = _classify(line)
        last = index == last_index
        if kind == "bad":
            if last and (not ends_nl or _partial_iter(line)):
                truncated = True
                continue
            _die(path, line, language)
        if kind == "cv":
            if seen["cv"]:
                _die(path, line, language)
            seen["cv"] = True
            row["k"] = payload[0]
            row["cv_error"] = payload[1]
        elif kind == "seed":
            if seen["seed"]:
                _die(path, line, language)
            seen["seed"] = True
            row["seed"] = payload
        elif kind == "loglik":
            if seen["loglik"]:
                _die(path, line, language)
            seen["loglik"] = True
            row["loglik"] = payload
        elif kind == "converged":
            if seen["converged"]:
                _die(path, line, language)
            seen["converged"] = True
            row["iterations"] = payload
            row["converged"] = "yes"
    if not ends_nl:
        truncated = True
    row["warnings"] = _warn(path, language, not seen["cv"], truncated)
    return [row]


def parse_admixture_log(path, *, language="en"):
    """Return rows for one ADMIXTURE stdout file or a CV-only text file.

    ``language`` is keyword-only. ``en`` is the default. ``zh`` selects
    the Chinese warning and error text. The ``file`` field is ``path``.
    """
    path = os.fspath(path)
    if not os.path.isfile(path):
        raise SystemExit(_msg("log_not_found", language, path=path))
    with open(path, "rb") as handle:
        raw = handle.read()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")
    ends_nl = raw.endswith(b"\n")
    lines = text.splitlines()
    banner = any("ADMIXTURE Version" in line for line in lines)
    if not banner:
        return _parse_cv_only(path, lines, language)
    return _parse_banner(path, lines, ends_nl, language)


def _dir_logs(item):
    first = sorted(glob.glob(os.path.join(item, "*.out")))
    hits = list(first)
    seen_real = {os.path.realpath(f) for f in first}
    for candidate in sorted(glob.glob(os.path.join(item, "*.log"))):
        key = os.path.realpath(candidate)
        if key in seen_real:
            continue
        seen_real.add(key)
        hits.append(candidate)
    return hits


def collect_logs(items, *, language="en"):
    """Collect log paths the way ``collect_q`` collects Q files.

    A directory contributes ``*.out`` then ``*.log``, each sorted, and
    skips a later path whose real path was already taken.
    """
    files = []
    for item in items:
        if os.path.isdir(item):
            hits = _dir_logs(item)
            if not hits:
                raise SystemExit(_msg("logs_dir_empty", language, path=item))
        else:
            hits = sorted(glob.glob(item))
            if not hits:
                if any(ch in item for ch in "*?["):
                    raise SystemExit(_msg("logs_no_match", language, item=item))
                hits = [item]
        files.extend(hits)
    uniq = []
    seen = set()
    for candidate in files:
        if candidate not in seen:
            seen.add(candidate)
            uniq.append(candidate)
    if not uniq:
        raise SystemExit(_msg("logs_none", language))
    return uniq


def check_logs_map(map_path, log_paths, *, language="en"):
    """Check a two-column log and Q map. Do not write a pairing file."""
    map_path = os.fspath(map_path)
    if not os.path.isfile(map_path):
        raise SystemExit(_msg("logs_map_missing", language, path=map_path))
    pairs = []
    seen = set()
    with open(map_path, encoding="utf-8") as handle:
        for raw in handle:
            line = raw.rstrip("\r\n")
            parts = line.split()
            if len(parts) != 2:
                raise SystemExit(_msg("logs_map_line", language, path=map_path, line=line))
            log_path, q_path = parts
            if log_path in seen:
                raise SystemExit(_msg("logs_map_dup", language, path=log_path))
            seen.add(log_path)
            pairs.append((log_path, q_path))
    have = set(log_paths)
    for log_path, _q_path in pairs:
        if log_path not in have:
            raise SystemExit(_msg("logs_map_not_in_logs", language, path=log_path))
    for _log_path, q_path in pairs:
        if not os.path.isfile(q_path):
            raise SystemExit(_msg("logs_map_q_missing", language, path=q_path))
    for log_path in log_paths:
        if log_path not in seen:
            raise SystemExit(_msg("logs_map_no_row", language, path=log_path))


def write_cv_loglik_tsv(path, rows):
    """Write the eight-column CV table. No Q path column."""
    lines = ["\t".join(_COLUMNS)]
    for row in rows:
        lines.append("\t".join(row[name] for name in _COLUMNS))
    text = "\n".join(lines) + "\n"
    folder = os.path.dirname(os.path.abspath(path))
    if folder:
        os.makedirs(folder, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
