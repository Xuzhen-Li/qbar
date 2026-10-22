# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## Unreleased

The package version is 0.2.0.dev0. No git tag exists.

### Added

- `CONTRIBUTING.md`, the Contributor Covenant 2.1 code of conduct, a bug-report template, and a pull-request template.
- `CITATION.cff` and `.zenodo.json` describe version 0.2.0.dev0. No release date is set, because there is no release.
- GitHub Actions installs the package and runs the tests on ubuntu-latest and macos-latest for Python 3.9 and 3.14. The workflow does not compare PNG or PDF bytes (58369c4).
- The unit tests can import an installed qbar when `QBAR_TEST_INSTALLED` is `1` (93951eb).
- The pip distribution name is qbar-plot. The `qbar` command runs the same program (a2a83d8).
- qbar can be imported. The implementation lives under src/qbar. `python qbar.py` still runs the same command (8b361b1).
- `tools/run_demo_cases.sh` runs the demo cases, and `tools/compare_outputs.py` compares two output directories (cc6eefd).
- Alignment methods, an align report, hclust options, and the full README (fe7a173, GitHub pull request #6).
- The full-group order file used in the README example (adbe3a0).
- A beginner README with screenshots (cd615f6).
- An English README, with the Chinese text kept in `README.zh.md` (9b7270c).

### Changed

- An --ids line with more than one whitespace-separated token still uses the first token as the ID. qbar warns on stderr with how many lines did that, and shows the first example. Output files are unchanged (584b084).
- A directory given to --q now includes lowercase .q files as well as .Q files. .Q files stay in the same sorted order, and the same file is not added twice (6471e3b).
- Both READMEs state the no-align anchor exception (76c8d62).
- State that core mode needs qmax at both adjacent K (55febd8).
- Document comma and equals limits on group names (76bbd3f).
- List the README options that --help already has (3aca7cd).
- Document the loaded Q value bounds (7ba5f17).
- Document the core-mode purest-person fallback (c1c5b59).
- State that no-align still applies the anchor (a579357).
- Say the align-mode mask is shared by every method (b872c82).
- Dispatch pong and jaccard inside match_next (2ef55fb).
- Update the module docstring to describe all alignment methods (305f5d5).
- Restore the DOI, the hclust method, and the output list in the README (cf69fa0).
- Remove an unused align screenshot, and note that a single-K run does not write align.tsv (e6266aa, GitHub pull request #1).
- Remove the duplicate align section from the README (1d78f6d).
- Point the order-file example at `demo/2448/order.txt` (a5820ea).
- Polish the README and add an order-file example (3bcbd00).
- Rewrite the Chinese README text so readers can follow it. At this commit that text was still `README.md` (2ceb1b7).

### Fixed

- Pearson correlation is 0 when either column is constant. Centering a constant float column is not always an exact zero, so those columns used to score about 1 or about -1 (c25f65f).
- When groups share the highest column mean, the legend keeps the group that appears first in the sample list. An exact tie no longer follows hash order (97bfe75).
- A Q matrix that contains NaN stops with an error instead of being drawn. Inf is still rejected by the range check (b9d8639).
- A one-row Q file stays one row, and a one-column file stays one column. A one-row file used to be read as one column, so each proportion was treated as a different person. A file with one number is one person and K=1 (9b00ec4).
- Drop the deprecated Pillow fromarray mode argument (ff8d660).
- Warn on stderr when a group name is too narrow to draw (abe34ca).
- Do not call a tied or low-confidence column a split (9b023d0).
- Flag low confidence from the printed similarity (2dbabc4).
- Name the Q file when it is not whitespace-separated numbers (19bea3c).
- Exit when an hclust distance is not finite (963295f).
- Remove the undefined c_align name (ab8374f).

## 0.1.0 - 2026-10-11

No git tag exists for 0.1.0. This heading is the initial public commit 58c7a27 (2026-10-11). The commit message is "Initial release of qbar".

### Added

- `qbar.py`, `test_qbar.py`, `requirements.txt`, the `demo/2448` inputs, `demo/README.md`, a Chinese `README.md`, `.gitignore`, and the MIT license (58c7a27).
