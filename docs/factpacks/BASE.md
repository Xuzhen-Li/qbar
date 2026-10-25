# BASE. Flags already on the parser

Date: 2026-10-24. This note records five options that were already on `build_parser` and did not appear in any earlier file under `docs/factpacks/`. They are `--qmax`, `--anchor-group`, `--title`, `--width`, and `--bar-height`. No new flag is added. The defaults below are the ones the parser already had.

## What each flag does

`--qmax` is a float. `build_parser` sets the default to 0.75. The help text is `qmax cutoff for core mode. Default 0.75`. `qbar.align.core_mask` keeps a person when that person's maximum at both K is strictly greater than this cutoff, inside each group named by `--align-groups`. If a listed group has nobody above the cutoff, that group's purest person at the lower K is kept. The default `--align-mode` is `all`, and that mode does not apply this cutoff. Mode `core` requires `--align-groups`. The message is `align-mode core requires --align-groups`.

`--anchor-group` defaults to an empty string. `qbar.align.anchor_perm` keeps the people in that group, takes the one with the highest maximum, and places that person's largest column first. The help text says that, when aligning, only the lowest K is changed this way, and that with `--no-align`, or when there is only one K, every K is changed this way.

`--title` defaults to an empty string. `build_parser` registers it with no help string. `qbar.plot_static.render` draws the string above the figure when the string is non-empty.

`--width` defaults to 2200. The help text is `Bar plot width, in pixels`. `render` receives that integer as the bar width.

`--bar-height` defaults to 0. The help text says the height of each bar row is 220 for a single K and 120 when there is more than one K. In `qbar.api.run`, a non-zero `--bar-height` is that height, and 0 means 220 for one K and 120 for more than one K. When several K are drawn, each `bar_K*.png` uses the maximum of that height and 180, and `panel.png` uses the height itself.

## Commands

Both commands are run from the repository root on the same two bundled demo files. The first sets none of the five flags.

```bash
qbar \
  --q demo/2448/ref2448_pruned.2.Q demo/2448/ref2448_pruned.3.Q \
  --fam demo/2448/ref2448_pruned.fam \
  --groups demo/2448/groups.tsv \
  --id-col id \
  --group-col group \
  --outdir out/base-default
```

`align.tsv`:

```text
K_to	n_mask	pearson
3	2448	0.995 0.748
```

`perm_K2.tsv`:

```text
C	raw	hex	owners
C1	1	#4470b7	W-Ad+WWE1+WWE2
C2	2	#dc1f26	C-Ad+CG1+CG2+CG3+CG4+CG5+CG6+WEE1+WEE2
```

The second command sets all five. `--align-mode core` and `--align-groups WWE1` are set so `--qmax` is the cutoff `core_mask` reads. `--qmax` is `0.95` in this command. The parser default remains 0.75.

```bash
qbar \
  --q demo/2448/ref2448_pruned.2.Q demo/2448/ref2448_pruned.3.Q \
  --fam demo/2448/ref2448_pruned.fam \
  --groups demo/2448/groups.tsv \
  --id-col id \
  --group-col group \
  --align-mode core \
  --align-groups WWE1 \
  --qmax 0.95 \
  --anchor-group WEE1 \
  --title Base \
  --width 800 \
  --bar-height 60 \
  --outdir out/base-flags
```

`align.tsv`:

```text
K_to	n_mask	pearson
3	129	0.899 0.971
```

`perm_K2.tsv`:

```text
C	raw	hex	owners
C1	2	#4470b7	C-Ad+CG1+CG2+CG3+CG4+CG5+CG6+WEE1+WEE2
C2	1	#dc1f26	W-Ad+WWE1+WWE2
```

`perm_K3.tsv`:

```text
C	raw	hex	owners
C1	2	#4470b7	C-Ad+CG3+CG4+CG5+CG6
C2	3	#dc1f26	W-Ad+WWE1+WWE2
C3	1	#981b1e	CG1+CG2+WEE1+WEE2
```

`args.txt` from this command contains:

```text
--align-mode core --align-groups WWE1 --qmax 0.95 --anchor-group WEE1 --title Base --width 800 --bar-height 60
```

Neither command wrote a warning on stderr. Both printed a terminal line ending in `panel.png`.
