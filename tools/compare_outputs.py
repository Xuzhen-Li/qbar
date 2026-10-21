#!/usr/bin/env python3
"""Compare two output roots.

PNG, TSV, and TXT files must be SHA256-identical.
args.txt and _stdout.txt are compared after each side's output root and
output-root/<case> paths are replaced with <OUTROOT>. On the first line of
args.txt, a leading path whose final component is qbar.py or qbar is replaced
with qbar.py, so python qbar.py and the installed qbar command compare equal.
A match is reported as identical-after-path-normalisation and is not a difference.
PDF files must match after /CreationDate and /ModDate entries are removed.
_stderr.txt is compared after qbar.py:<digits> is rewritten to qbar.py:N.
It is reported on its own and does not change the exit status.
Any other missing, extra, or different file makes the exit status 1.
"""

import hashlib
import os
import re
import sys

# Pillow writes "/CreationDate (D:YYYYMMDDHHMMSSZ)" and the same form for ModDate.
_PDF_DATE_ENTRY = re.compile(
    br"/(?:CreationDate|ModDate)[ \t]+\([^)\r\n]*\)"
)
_QBAR_LINE = re.compile(br"qbar\.py:\d+")
_PATH_FILES = ("args.txt", "_stdout.txt")


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def pdf_without_dates(data):
    return _PDF_DATE_ENTRY.sub(b"", data)


def case_dirs(root):
    if not os.path.isdir(root):
        return {}
    found = {}
    for name in sorted(os.listdir(root)):
        path = os.path.join(root, name)
        if os.path.isdir(path):
            found[name] = path
    return found


def files_under(directory):
    found = {}
    for dirpath, _dirnames, filenames in os.walk(directory):
        for name in filenames:
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, directory)
            found[rel] = full
    return found


def kind_of(rel):
    base = os.path.basename(rel)
    if base == "_stderr.txt":
        return "stderr"
    ext = os.path.splitext(base)[1].lower()
    if ext == ".png":
        return "png"
    if ext == ".tsv":
        return "tsv"
    if ext == ".txt":
        return "txt"
    if ext == ".pdf":
        return "pdf"
    return "other"


def normalise_outroot(data, root, case):
    """Replace this side's output root and output-root/<case> with <OUTROOT>."""
    text = data.decode("utf-8")
    case_dir = os.path.join(root, case)
    text = text.replace(case_dir, "<OUTROOT>")
    text = text.replace(root, "<OUTROOT>")
    return text.encode("utf-8")


def normalise_program_token(data):
    """Rewrite a leading qbar or qbar.py path to qbar.py."""
    text = data.decode("utf-8")
    line, sep, rest = text.partition("\n")
    token, gap, tail = line.partition(" ")
    if os.path.basename(token) in ("qbar.py", "qbar"):
        token = "qbar.py"
    return (token + gap + tail + sep + rest).encode("utf-8")


def compare_pair(rel, path_a, path_b, root_a, root_b, case):
    kind = kind_of(rel)
    base = os.path.basename(rel)
    with open(path_a, "rb") as handle:
        data_a = handle.read()
    with open(path_b, "rb") as handle:
        data_b = handle.read()
    detail = ""
    if base in _PATH_FILES:
        try:
            left = normalise_outroot(data_a, root_a, case)
            right = normalise_outroot(data_b, root_b, case)
            if base == "args.txt":
                left = normalise_program_token(left)
                right = normalise_program_token(right)
        except UnicodeDecodeError:
            left = data_a
            right = data_b
        if left == right:
            status = "identical-after-path-normalisation"
        else:
            status = "differ"
            detail = "sha256 %s %s" % (sha256(left)[:12], sha256(right)[:12])
    elif kind == "pdf":
        left = pdf_without_dates(data_a)
        right = pdf_without_dates(data_b)
        if left == right:
            status = "pdf-identical"
        else:
            status = "differ"
            detail = "sha256 %s %s ; after date strip sha256 %s %s" % (
                sha256(data_a)[:12],
                sha256(data_b)[:12],
                sha256(left)[:12],
                sha256(right)[:12],
            )
    elif kind == "stderr":
        left = _QBAR_LINE.sub(b"qbar.py:N", data_a)
        right = _QBAR_LINE.sub(b"qbar.py:N", data_b)
        if left == right:
            status = "stderr-identical"
        else:
            status = "stderr-differ"
            detail = "sha256 %s %s" % (sha256(left)[:12], sha256(right)[:12])
    else:
        if data_a == data_b:
            status = "identical"
        else:
            status = "differ"
            detail = "sha256 %s %s" % (sha256(data_a)[:12], sha256(data_b)[:12])
    return status, detail, kind


def main(argv):
    if len(argv) != 3:
        print("usage: compare_outputs.py OUTROOT_A OUTROOT_B", file=sys.stderr)
        return 2
    root_a = os.path.abspath(argv[1])
    root_b = os.path.abspath(argv[2])
    if not os.path.isdir(root_a) or not os.path.isdir(root_b):
        print("both OUTROOT paths must be directories", file=sys.stderr)
        print("A %s" % root_a, file=sys.stderr)
        print("B %s" % root_b, file=sys.stderr)
        return 2

    cases_a = case_dirs(root_a)
    cases_b = case_dirs(root_b)
    cases = sorted(set(cases_a) | set(cases_b))

    rows = []
    counts = {
        "identical": 0,
        "pdf-identical": 0,
        "identical-after-path-normalisation": 0,
        "differ": 0,
        "only-in-A": 0,
        "only-in-B": 0,
        "stderr-identical": 0,
        "stderr-differ": 0,
        "missing-case": 0,
    }

    for case in cases:
        if case not in cases_a or case not in cases_b:
            which = "only-in-A" if case in cases_a else "only-in-B"
            counts["missing-case"] += 1
            counts[which] += 1
            rows.append((case, "(directory)", which, ""))
            continue
        files_a = files_under(cases_a[case])
        files_b = files_under(cases_b[case])
        names = sorted(set(files_a) | set(files_b))
        for rel in names:
            if rel not in files_a:
                counts["only-in-B"] += 1
                rows.append((case, rel, "only-in-B", ""))
                continue
            if rel not in files_b:
                counts["only-in-A"] += 1
                rows.append((case, rel, "only-in-A", ""))
                continue
            status, detail, _kind = compare_pair(
                rel, files_a[rel], files_b[rel], root_a, root_b, case
            )
            counts[status] += 1
            rows.append((case, rel, status, detail))

    case_w = max([len("case")] + [len(r[0]) for r in rows] or [4])
    file_w = max([len("file")] + [len(r[1]) for r in rows] or [4])
    status_w = max([len("status")] + [len(r[2]) for r in rows] or [6])
    header = "%-*s  %-*s  %-*s  %s" % (case_w, "case", file_w, "file", status_w, "status", "detail")
    print(header)
    print("-" * len(header))
    for case, rel, status, detail in rows:
        print("%-*s  %-*s  %-*s  %s" % (case_w, case, file_w, rel, status_w, status, detail))

    print("")
    print(
        "summary identical=%d pdf-identical=%d identical-after-path-normalisation=%d "
        "differ=%d only-in-A=%d only-in-B=%d "
        "stderr-identical=%d stderr-differ=%d missing-case=%d"
        % (
            counts["identical"],
            counts["pdf-identical"],
            counts["identical-after-path-normalisation"],
            counts["differ"],
            counts["only-in-A"],
            counts["only-in-B"],
            counts["stderr-identical"],
            counts["stderr-differ"],
            counts["missing-case"],
        )
    )
    print("A %s" % root_a)
    print("B %s" % root_b)

    failed = counts["differ"] + counts["only-in-A"] + counts["only-in-B"]
    if failed:
        print("result DIFFERENCES %d" % failed)
        return 1
    print("result IDENTICAL")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
