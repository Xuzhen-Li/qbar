# Web page

A static page under `web/` runs this repository's qbar package in the browser. The command-line program is unchanged. `--palette` stays `science`, `--id-col` stays `analysis_IID`, and `--group-col` stays `Dong_Grp`. A push to `main` does not publish the page. Versioned hosting is under Hosting below.

## What the page does

The page has three steps.

1. Load Q files, one sample file (`--fam` or `--ids`), and an optional groups file. The ID and group column names start as the command-line defaults. A blank field keeps that default.
2. Choose a K range from the loaded file names, and an align method. The default method is `greedy`. After the status says ready, the method list is `qbar.align.ALIGN_METHODS` from the wheel.
3. Run, view the bar PNGs, and download files. `--vector` is `off` unless you choose `pdf`, `svg`, or `both`.

The run writes each uploaded file under `/in` in the browser filesystem, using the base name only. It builds the argparse namespace with `qbar.cli.build_parser` and calls `qbar.api.run`. That is the entry the architecture note names. `cli.main` is not used, and the page does not read a config file. The output directory is `/out`. The page passes `--editor` so the package writes `state.json`. It does not pass `--palette`, `--within`, or the other flags, so those stay at the command-line defaults. The align method, the vector choice, and the groups column names are the fields on the form.

Pyodide runs in a Web Worker, and this release requires a module worker. The page stays responsive while a run is going.

After a successful run the thread calls `qbar.state.colours_tsv` and writes `colours.tsv`. Downloads are the output files, including one PNG per K, `order.tsv`, `colours.tsv`, and `state.json`. PDF or SVG files appear when `--vector` is not `off` and the run finishes. Each file is its own download. A zip is not offered.

The equivalent-command box is the same files and flags, with base names, plus `--state state.json`. It does not include `--editor`. That command is the replay command.

Errors from qbar, including `SystemExit` text, are shown as text. A row-count mismatch uses qbar's own message, which names both the Q row count and the sample-list count.

The status line is one of: loading, ready, running, done, error.

The footer reads `web/dist/build-info.json` and shows `qbar <version> (commit <12-char sha>)`. That file is fetched from this same server before the worker starts, so the read finishes before the status says ready. The version is `__version__` in `src/qbar/__init__.py`. The commit is the full SHA from `git rev-parse HEAD` at build time, and the page shows the first 12 characters. When `git status --porcelain` is not empty, the line adds ` dirty`.

## Privacy

Your files stay in this browser. They are not uploaded. The page loads one pinned Pyodide build and the local qbar wheel while the status says loading. After the status says ready, the page does not make another network request. The run and the downloads stay in this browser.

What that sentence covers: before ready, the page loads the pinned Pyodide files, the qbar wheel, and `build-info.json` from this same server (`web/dist/`). Those are files the build wrote. After ready, the run reads only the files you chose and the in-browser filesystem. Downloads use local object URLs. The page does not load fonts, images, or analytics, and it has no link that fetches a page on its own. What a local browser check saw, and what it could not see, is in `docs/factpacks/F10.md`. `web/tests/` checks that a run does not request any host other than `127.0.0.1`.

## Build

From the repository root:

```bash
python tools/build_web.py
```

That runs `pip wheel --no-deps` and writes `web/dist/<wheel>` plus `web/dist/manifest.json`. The manifest names the wheel and its sha256. The page checks that sha256 before it installs the wheel. A mismatch is an error. The same command writes `web/dist/build-info.json` with the version, the full commit SHA, a dirty flag, and the footer line.

The same command downloads the pinned Pyodide 314.0.7 files into `web/dist/pyodide/` from the source URL in `web/pyodide-pins.json` (jsDelivr, checked 2026-10-24). It checks each file's sha256 and size against that pin file before the file keeps its final name. A download that does not match is not renamed into place. A file that is already there and does not match is left in place and the command stops. The package wheels are also checked against the sha256 values in the pinned `pyodide-lock.json`. `web/dist/` is listed in `.gitignore` and is not part of a commit.

On 2026-10-24 that download was 9 files and 31674817 bytes: `pyodide.mjs`, `pyodide.asm.mjs`, `pyodide.asm.wasm`, `python_stdlib.zip`, `pyodide-lock.json`, and the wheels for micropip 0.11.1, numpy 2.4.6, pillow 12.2.0, and scipy 1.18.0. The lock file gives scipy a dependency on numpy and no further dependencies for these four packages.

A second run, when those files already match the pins, downloads none of them.

`python tools/build_web.py --offline OUTDIR` adds `--no-index` and `--no-build-isolation` for the wheel and does not download Pyodide. It needs a build backend that is already installed for that interpreter. If a pinned file is missing it exits 3 after the wheel manifest is written. If a pinned file is present and does not match, it exits 1 and leaves that file in place.

## Serve

The page is a set of files. Serve `web/` with the standard-library server:

```bash
python -m http.server --directory web 8000
```

Then open `http://127.0.0.1:8000/`. Build the wheel first. If `web/dist/manifest.json` is missing, the status stays on error and the message says to build the wheel.

Opening the HTML file directly, without that server, will not load the worker or the wheel.

## Pinned runtime

Checked on 2026-10-24. The newest stable Pyodide release whose lock file lists numpy, scipy, and pillow is 314.0.7.

| Piece | Version |
| --- | --- |
| Pyodide | 314.0.7 |
| Python | 3.14.2 |
| numpy | 2.4.6 |
| scipy | 1.18.0 |
| pillow | 12.2.0 |
| micropip | 0.11.1 |

The page sets `indexURL` to `./dist/pyodide/`, which is this server. It does not load Pyodide from a CDN at runtime.

Build time checks every pinned file's sha256 and size, including the runtime files and the package wheels. It also checks that each needed wheel's sha256 in `web/pyodide-pins.json` is the sha256 in `pyodide-lock.json`.

Load time, in the browser: Pyodide 314.0.7 `loadPyodide` has no `checkIntegrity` option. `loadPackage` takes `checkIntegrity`, and the default is true. The page passes `checkIntegrity: true`. That checks each package wheel against the sha256 in the lock file. The runtime files themselves are not covered by that package check. Their check is the build-time pin.

In Node, this Pyodide build's file reader does not apply the integrity argument. `tools/web_check.mjs` therefore checks the same pin file before it loads that directory.

qbar's own dependencies are numpy, scipy, and Pillow. Those three names are in the lock file. The page also loads micropip so it can install the local wheel with dependencies turned off. Nothing else from outside the standard library is imported when the page runs.

## Size limit

200 MB means 200 * 1024 * 1024 bytes, which is 209715200. The total of the selected files is what counts. Above that, the page refuses and the message names the byte count and the limit. It does not drop files to get under the limit.

## Known limits

Vector PDF and SVG ask qbar for a TrueType file in `FONT_CANDIDATES`. Those paths are not in the browser filesystem, so `--vector` other than `off` stops with qbar's missing-font message and writes no figure. PNG uses Pillow's built-in font.

The page does not offer logs, replicates, polygon, map pies, auto groups, or a config file. Those stay at the command-line defaults, which is off or omitted.

No zip file is built. There is no time target. On 2026-10-24 a local browser check of 2000 samples, K from 2 to 10, took 2.046 s, 1.443 s, and 2.033 s from click to done. The request record and its limits are in `docs/factpacks/F10.md`.

K from and K to must both be integers when any Q file name includes a K. A blank value, or a value that is not an integer, is an error and the run does not start. It does not mean every K. File names with no K have no range. Those inputs stay unused and every such Q file is used.

`tools/web_check.mjs` runs the same argument list inside the pinned Pyodide directory, with no network inside the script, and compares the output with `tools/compare_outputs.py`. A difference exits nonzero unless it is on the allow list: `state.json` may differ only in `git_commit` (the command-line run records the checkout HEAD and the wheel records `unknown`); `editor.html` may differ only in that field; `args.txt` may differ in paths; PNG bytes may differ only when the pixels match; PDF bytes may differ only with the Pillow version reason. A PNG whose pixels differ fails the check. The full note is `docs/factpacks/F10.md`.

## Hosting

Serving the `web/` directory on your own machine is the way to use the page before a tag exists. `python -m http.server --directory web 8000` stays the local server.

`.github/workflows/pages.yml` runs only when a tag matching `v*.*.*` is pushed, or when someone starts that workflow by hand and types the tag. It checks out that tag, builds the page, and fails unless `build-info.json` `version` equals the tag with the leading `v` removed. It then runs the Playwright suite. The built page is published into a directory named after the tag on the `gh-pages` branch, for example `v0.3.0/`. Older version directories are kept. A root `index.html` on that branch lists those directories and links the latest. The workflow does not turn GitHub Pages on.

After the first publish, the repository owner turns the site on: Settings, Pages, Deploy from a branch, branch `gh-pages`, folder `/` (root). The site is then `https://xuzhen-li.github.io/qbar/` for the list, and `https://xuzhen-li.github.io/qbar/v0.3.0/` for that tag. The page under `web/` has no external URL. Publishing waits until a tag is approved. The package version is 0.3.0. A pushed tag `v0.3.0` is the publish step. GitHub Pages is still turned on by the repository owner (Settings, Pages, Deploy from branch `gh-pages`, folder `/`).

`.github/workflows/web.yml` builds the page and runs `web/tests/` on pull requests and on pushes to `main`. It does not publish.
