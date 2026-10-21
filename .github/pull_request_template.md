## Problem

## Change

## Tests

## Output check

One topic per pull request.

Add a `CHANGELOG.md` entry under `## Unreleased` when a user can see the change.

Default PNG, TSV, and TXT files should stay byte-identical on the same dependency set. PDF files are compared after `/CreationDate` and `/ModDate` are removed. Use `tools/compare_outputs.py`. Do not compare PNG or PDF bytes across different numpy or Pillow versions.

Do not use an en dash (U+2013) or an em dash (U+2014).
