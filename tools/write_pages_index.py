#!/usr/bin/env python3
"""Write the root index for a versioned static site.

The directory contains one subdirectory per published tag, named vX.Y.Z.
This script writes index.html there. It lists those directories and links
the latest. It replaces only index.html. It does not delete or rename any
other file or directory.
"""
from __future__ import annotations

import os
import re
import sys

_VERSION = re.compile(r"^v([0-9]+)\.([0-9]+)\.([0-9]+)$")


def version_names(root):
    found = []
    for name in os.listdir(root):
        path = os.path.join(root, name)
        if not os.path.isdir(path):
            continue
        match = _VERSION.fullmatch(name)
        if not match:
            continue
        key = tuple(int(part) for part in match.groups())
        found.append((key, name))
    found.sort()
    return [name for _key, name in found]


def index_html(names):
    lines = [
        "<!DOCTYPE html>",
        "<html lang=\"en\">",
        "<head>",
        "  <meta charset=\"utf-8\">",
        "  <title>qbar</title>",
        "</head>",
        "<body>",
        "  <h1>qbar</h1>",
        "  <p>Published versions of the static page. Each directory is one tag.</p>",
    ]
    if names:
        latest = names[-1]
        lines.append(
            "  <p>Latest: <a href=\"./%s/\">%s</a></p>" % (latest, latest)
        )
    else:
        lines.append("  <p>No version directory is published yet.</p>")
    lines.append("  <ul>")
    for name in names:
        lines.append("    <li><a href=\"./%s/\">%s</a></li>" % (name, name))
    lines.append("  </ul>")
    lines.append("</body>")
    lines.append("</html>")
    lines.append("")
    return "\n".join(lines)


def write_index(root):
    names = version_names(root)
    path = os.path.join(root, "index.html")
    text = index_html(names)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    return names


def main(argv):
    if len(argv) != 2:
        print("usage: python tools/write_pages_index.py DIR", file=sys.stderr)
        return 2
    root = argv[1]
    if not os.path.isdir(root):
        print("not a directory: %s" % root, file=sys.stderr)
        return 1
    names = write_index(root)
    print("listed %d version directories" % len(names))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
