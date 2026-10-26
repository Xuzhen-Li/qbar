# qbar documentation

qbar is a command-line tool that reads ADMIXTURE Q matrix files (.Q), sorts samples, aligns columns across K values, and draws population structure bar plots in PNG and PDF formats. An ADMIXTURE Q matrix file is a table that shows how much of each sample's genetic makeup comes from each ancestral group, where K is the number of ancestral groups tested.

## Install

qbar needs Python 3, numpy, and Pillow. scipy is needed only for `--within hclust` or `--within-group X=hclust` (and all `--hclust-*` options), and for `--align-method` `hungarian`, `pong` and `jaccard`. Hclust (hierarchical clustering) groups similar samples together automatically, while alignment methods like greedy, hungarian, pong, and jaccard are different mathematical ways to match ancestral group columns from K-1 to K. Default greedy alignment and everything else need only numpy and Pillow, though scipy is already in `requirements.txt`.

```bash
git clone https://github.com/Xuzhen-Li/qbar.git
cd qbar
```

The README Install section then creates a virtual environment, activates it, and runs `python3 -m pip install -r requirements.txt`.

After the first PyPI release, install the package with:

```bash
pip install qbar-plot
```

That command is not available before the first PyPI release. From a checkout of this repository, install the same package with:

```bash
pip install .
```

The installed command is `qbar`. `python3 qbar.py` still runs the program from a checkout.

## Guides

- [Command line](cli.md) is generated from the argument parser.
- [Choosing an alignment method](choosing-alignment-method.md) describes the alignment methods.
- [Web page](web.md) describes the static page and versioned GitHub Pages hosting.
- [Tutorial](tutorial.md) walks through the bundled demo, one step at a time.

## Fact packs

Each file under [factpacks/](factpacks/) records one change: the flags, the files, and an example that was run. `BASE` records flags that were already on the parser and were not named in an earlier pack. `S11` records this index, the tutorial, and the check that every long option appears in `cli.md` and in some fact pack.

| ID | Title | Flags it adds |
| --- | --- | --- |
| [BASE](factpacks/BASE.md) | Flags already on the parser | `--qmax`, `--anchor-group`, `--title`, `--width`, `--bar-height` |
| [S1](factpacks/S1.md) | Replicates and modes | `--replicates`, `--mode-sim-cut` |
| [S2](factpacks/S2.md) | More input formats | `--q-format`, `--ind` |
| [S3](factpacks/S3.md) | English CLI | `--language` |
| [S4](factpacks/S4.md) | Colours across K, and a greyscale check | `--palette`, `--color-lock`, `--greyscale-preview` |
| [S5](factpacks/S5.md) | Vector PDF and SVG | `--vector` |
| [S6](factpacks/S6.md) | Map pies | `--sites`, `--basemap-image`, `--basemap-bbox` |
| [S7](factpacks/S7.md) | YAML config | `--config` |
| [S8](factpacks/S8.md) | Python API | none |
| [S9](factpacks/S9.md) | Speed at 10k to 100k | none |
| [S10](factpacks/S10.md) | Provenance | `--provenance` |
| [S12](factpacks/S12.md) | Exports for other tools | `--export` |
| [F1](factpacks/F1.md) | Hierarchical clustering across samples or groups | `--order-mode`, `--group-order`, `--dendrogram`, `--hclust-max-bytes` |
| [F2](factpacks/F2.md) | Index of F2a to F2e | `--align-method` values in F2a to F2d, and `--align-compare` |
| [F2a](factpacks/F2a.md) | clumpp-full | `--align-method` value `clumpp-full` |
| [F2b](factpacks/F2b.md) | clumpp-greedy | `--align-method` value `clumpp-greedy` |
| [F2c](factpacks/F2c.md) | clumpp-largek | `--align-method` value `clumpp-largek` |
| [F2d](factpacks/F2d.md) | clumppling-ilp | `--align-method` value `clumppling-ilp` |
| [F2e](factpacks/F2e.md) | align-compare | `--align-compare` |
| [F3](factpacks/F3.md) | Standalone HTML with hover | `--html` |
| [F4](factpacks/F4.md) | Simplex polygon plot | `--polygon`, `--polygon-k` |
| [F5](factpacks/F5.md) | CV error and log-likelihood | `--logs`, `--logs-map` |
| [F6](factpacks/F6.md) | Select-K heuristics | `--select-k`, `--plateau-fraction` |
| [F7](factpacks/F7.md) | Cluster tracking across K | `--cluster-flow`, `--flow-weight` |
| [F8](factpacks/F8.md) | Groups, including data-driven groups | `--auto-groups`, `--auto-k`, `--admix-cut`, `--auto-g`, `--auto-seed`, `--pca`, `--pca-n` |
| [F9](factpacks/F9.md) | Manual editor and replayable state | `--editor`, `--state` |
| [F10](factpacks/F10.md) | Static page | none |
| [ST1](factpacks/ST1.md) | Bootstrap support for a column match | `--bootstrap`, `--bootstrap-seed` |
| [ST2](factpacks/ST2.md) | Permutation p value per match | `--perm`, `--perm-seed`, `--perm-null` |
| [ST3](factpacks/ST3.md) | Simulation-calibrated low-confidence cuts | `--low-confidence-table` |
| [ST4](factpacks/ST4.md) | Parent-share interval, and one parent versus two | `--parent-ci`, `--parent-alpha`, `--parent-test` |
| [S11](factpacks/S11.md) | Documentation index and tutorial | none |
