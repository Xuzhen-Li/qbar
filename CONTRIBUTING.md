# Contributing

## Tests

From a checkout, in the repository root:

```bash
python3 -m unittest test_qbar.py
```

That command imports the root `qbar.py` launcher.

To test an installed copy, install this checkout with `python3 -m pip install .` and set `QBAR_TEST_INSTALLED` to `1`. From the repository root:

```bash
QBAR_TEST_INSTALLED=1 python3 -m unittest test_qbar.py
```

From another directory, run the checkout's test file with the interpreter that has qbar installed:

```bash
QBAR_TEST_INSTALLED=1 python3 /path/to/the/checkout/test_qbar.py
```

When the variable is `1`, the test removes its own directory from `sys.path` before `import qbar`.

## Pull requests

One topic per pull request.

A user-visible change gets an entry under `## Unreleased` in `CHANGELOG.md`.

Default output should stay byte-identical for PNG, TSV, and TXT files, and PDF files should match after `/CreationDate` and `/ModDate` are removed. Compare two output directories with:

```bash
python3 tools/compare_outputs.py DIR_A DIR_B
```

PNG and PDF bytes can differ when numpy or Pillow differ, even when every TSV and TXT file matches. Compare image bytes only within one dependency set. The tool reports `_stderr.txt` on its own, and that file alone does not change the exit status.

Do not use an en dash (U+2013) or an em dash (U+2014) in files added to this repository. Use a comma, the word "to", "..", or a plain hyphen.
