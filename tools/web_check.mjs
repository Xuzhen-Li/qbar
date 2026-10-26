#!/usr/bin/env node
// Run one fixture through the same Pyodide entry the page uses, then
// compare that directory with a command-line run. This file does not
// fetch anything. The Pyodide directory on the command line must already
// contain the runtime and the numpy, scipy, pillow, and micropip wheels.

import fs from "node:fs";
import path from "node:path";
import { createHash } from "node:crypto";
import { spawnSync } from "node:child_process";
import { fileURLToPath, pathToFileURL } from "node:url";

import { buildJobArgv, filenameK } from "../web/page_argv.mjs";
import { bootRuntime, installWheel, runQbar } from "../web/worker.js";

const repo = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const scriptPath = fileURLToPath(import.meta.url);

export const BAR_LEFT = 56;
export const DEFAULT_BAR_WIDTH = 2200;

export function barWidthFromArgv(argv) {
  const list = argv || [];
  for (let i = 0; i < list.length; i++) {
    if (list[i] !== "--width") {
      continue;
    }
    const value = Number(list[i + 1]);
    if (Number.isInteger(value) && value >= 1) {
      return value;
    }
  }
  return DEFAULT_BAR_WIDTH;
}

const PNG_PIXELS_PY = [
  "from PIL import Image",
  "import sys",
  "a = Image.open(sys.argv[1])",
  "b = Image.open(sys.argv[2])",
  "bar_w = int(sys.argv[3])",
  "left = 56",
  "if a.size == b.size and a.mode == b.mode and list(a.getdata()) == list(b.getdata()):",
  "    print('pixels-identical')",
  "    raise SystemExit(0)",
  "aw, ah = a.size",
  "bw, bh = b.size",
  "x0 = left",
  "x1 = left + bar_w",
  "y0 = 8",
  "y1 = min(ah, bh) - 48",
  "req_w = x1 - x0",
  "req_h = y1 - y0",
  "fit = (",
  "    ah == bh and aw >= x1 and bw >= x1 and ah >= 56 and bh >= 56",
  "    and a.mode == b.mode and req_w > 0 and req_h > 0",
  "    and x1 <= aw and y1 <= ah and x1 <= bw and y1 <= bh",
  ")",
  "mismatch = 0",
  "if req_w > 0 and req_h > 0:",
  "    def overlap(im):",
  "        w, h = im.size",
  "        ix0 = min(w, max(x0, 0))",
  "        iy0 = min(h, max(y0, 0))",
  "        ix1 = min(w, max(x1, 0))",
  "        iy1 = min(h, max(y1, 0))",
  "        if ix1 < ix0:",
  "            ix1 = ix0",
  "        if iy1 < iy0:",
  "            iy1 = iy0",
  "        return ix0, iy0, ix1, iy1",
  "    ax0, ay0, ax1, ay1 = overlap(a)",
  "    bx0, by0, bx1, by1 = overlap(b)",
  "    cx0, cy0 = max(ax0, bx0), max(ay0, by0)",
  "    cx1, cy1 = min(ax1, bx1), min(ay1, by1)",
  "    common = 0",
  "    differ = 0",
  "    if cx1 > cx0 and cy1 > cy0 and a.mode == b.mode:",
  "        pa = list(a.crop((cx0, cy0, cx1, cy1)).getdata())",
  "        pb = list(b.crop((cx0, cy0, cx1, cy1)).getdata())",
  "        common = len(pa)",
  "        differ = sum(1 for i in range(common) if pa[i] != pb[i])",
  "    elif cx1 > cx0 and cy1 > cy0:",
  "        differ = (cx1 - cx0) * (cy1 - cy0)",
  "        common = differ",
  "    mismatch = differ + (req_w * req_h - common)",
  "if fit and mismatch == 0:",
  "    print('crop-match %d %d' % (aw, bw))",
  "elif fit:",
  "    print('crop-mismatch %d' % mismatch)",
  "else:",
  "    print('crop-unfit %d' % mismatch)",
].join("\n");

function comparePng(leftPath, rightPath, barW, python) {
  const pixel = spawnSync(python, ["-c", PNG_PIXELS_PY, leftPath, rightPath, String(barW)], {
    encoding: "utf8",
  });
  const note = pixel.status === 0 ? pixel.stdout.trim() : "";
  if (note === "pixels-identical") {
    return { kind: "pixels" };
  }
  const match = /^crop-match (\d+) (\d+)$/.exec(note);
  if (match) {
    return { kind: "crop-match", aw: Number(match[1]), bw: Number(match[2]) };
  }
  const mismatch = /^crop-mismatch (\d+)$/.exec(note);
  if (mismatch) {
    return { kind: "crop-mismatch", count: Number(mismatch[1]) };
  }
  const unfit = /^crop-unfit (\d+)$/.exec(note);
  if (unfit) {
    return { kind: "crop-unfit", count: Number(unfit[1]) };
  }
  return { kind: "failed", note: "pixel-compare-failed" };
}

// files: { rel, leftPath, rightPath, sameBytes } for PNG and PDF names.
// A missing side uses null. sameBytes is meaningful only when both paths exist.
export function classifyOutputDiffs(files, options) {
  const barW = options && Number.isInteger(options.barW) ? options.barW : DEFAULT_BAR_WIDTH;
  const python = options && options.python;
  const explained = [];
  const unexpected = [];
  let pngCount = 0;
  let pngFailed = false;
  const pdfs = [];
  for (let i = 0; i < files.length; i++) {
    const file = files[i];
    const ext = path.extname(file.rel).toLowerCase();
    if (ext === ".pdf") {
      pdfs.push(file);
      continue;
    }
    if (ext !== ".png") {
      continue;
    }
    pngCount += 1;
    if (!file.leftPath || !file.rightPath) {
      pngFailed = true;
      unexpected.push(file.rel + " missing on one side");
      continue;
    }
    if (file.sameBytes) {
      continue;
    }
    const verdict = comparePng(file.leftPath, file.rightPath, barW, python);
    if (verdict.kind === "pixels") {
      explained.push(file.rel + " bytes differ and pixels match");
    } else if (verdict.kind === "crop-match") {
      explained.push(
        file.rel + " bar crop matches; widths " + verdict.aw + " and " + verdict.bw
      );
    } else if (verdict.kind === "crop-mismatch") {
      pngFailed = true;
      unexpected.push(file.rel + " crop mismatch " + verdict.count);
    } else if (verdict.kind === "crop-unfit") {
      pngFailed = true;
      unexpected.push(file.rel + " crop does not fit; mismatch " + verdict.count);
    } else {
      pngFailed = true;
      unexpected.push(file.rel + " " + verdict.note);
    }
  }
  const pngsAllowPdf = pngCount > 0 && !pngFailed;
  for (let i = 0; i < pdfs.length; i++) {
    const file = pdfs[i];
    if (!file.leftPath || !file.rightPath) {
      unexpected.push(file.rel + " missing on one side");
      continue;
    }
    if (file.sameBytes) {
      continue;
    }
    if (pngsAllowPdf) {
      explained.push(file.rel + " bytes differ; every PNG bar crop matches");
    } else if (pngCount === 0) {
      unexpected.push(file.rel + " PDF bytes differ; there is no PNG");
    } else {
      unexpected.push(file.rel + " PDF bytes differ; a PNG bar crop does not match");
    }
  }
  return { explained: explained, unexpected: unexpected };
}

function usage() {
  console.error(
    "usage: node tools/web_check.mjs --pyodide DIR --dist DIR --out DIR " +
    "--python PYTHON --fixture DIR [--k-min N] [--k-max N] " +
    "[--id-col NAME] [--group-col NAME] [--method NAME] " +
    "[--vector off|pdf|svg|both]"
  );
  process.exit(2);
}

function parseArgs(argv) {
  const out = {
    kMin: null,
    kMax: null,
    idCol: "analysis_IID",
    groupCol: "Dong_Grp",
    method: "greedy",
    vector: "off",
  };
  for (let i = 2; i < argv.length; i++) {
    const flag = argv[i];
    const value = argv[i + 1];
    if (value === undefined || value.indexOf("--") === 0) {
      usage();
    }
    if (flag === "--pyodide") out.pyodide = value;
    else if (flag === "--dist") out.dist = value;
    else if (flag === "--out") out.out = value;
    else if (flag === "--python") out.python = value;
    else if (flag === "--fixture") out.fixture = value;
    else if (flag === "--k-min") out.kMin = Number(value);
    else if (flag === "--k-max") out.kMax = Number(value);
    else if (flag === "--id-col") out.idCol = value;
    else if (flag === "--group-col") out.groupCol = value;
    else if (flag === "--method") out.method = value;
    else if (flag === "--vector") out.vector = value;
    else usage();
    i += 1;
  }
  if (!out.pyodide || !out.dist || !out.out || !out.python || !out.fixture) {
    usage();
  }
  return out;
}

function prepare(dir) {
  fs.mkdirSync(dir, { recursive: true });
  if (fs.readdirSync(dir).length) {
    throw new Error("refuse: output directory is not empty");
  }
}

function collectFixture(dir, kMin, kMax) {
  const names = fs.readdirSync(dir).sort();
  const files = [];
  for (let i = 0; i < names.length; i++) {
    const name = names[i];
    const full = path.join(dir, name);
    if (!fs.statSync(full).isFile()) {
      continue;
    }
    const lower = name.toLowerCase();
    let role = null;
    if (lower.endsWith(".q") || lower.endsWith(".meanq") || lower.endsWith(".qopt")) {
      role = "q";
    } else if (lower.endsWith(".fam")) {
      role = "fam";
    } else if (name === "groups.tsv" || name === "groups.csv") {
      role = "groups";
    }
    if (!role) {
      continue;
    }
    if (role === "q" && kMin !== null && kMax !== null) {
      const k = filenameK(name);
      if (k !== null && (k < kMin || k > kMax)) {
        continue;
      }
    }
    files.push({
      role: role,
      name: name,
      bytes: new Uint8Array(fs.readFileSync(full)),
      hostPath: full,
    });
  }
  return files;
}

function writeTree(dir, files) {
  for (let i = 0; i < files.length; i++) {
    const dest = path.join(dir, files[i].name);
    fs.mkdirSync(path.dirname(dest), { recursive: true });
    fs.writeFileSync(dest, files[i].bytes);
  }
}

function listFiles(dir) {
  const found = {};
  function walk(current, prefix) {
    const names = fs.readdirSync(current).sort();
    for (let i = 0; i < names.length; i++) {
      const full = path.join(current, names[i]);
      const rel = prefix ? prefix + "/" + names[i] : names[i];
      if (fs.statSync(full).isDirectory()) {
        walk(full, rel);
      } else {
        found[rel] = full;
      }
    }
  }
  walk(dir, "");
  return found;
}

function sha256(file) {
  return createHash("sha256").update(fs.readFileSync(file)).digest("hex");
}

function verifyPinnedRuntime(dir) {
  const pins = JSON.parse(fs.readFileSync(path.join(repo, "web", "pyodide-pins.json"), "utf8"));
  const files = pins.files || {};
  const names = Object.keys(files);
  for (let i = 0; i < names.length; i++) {
    const name = names[i];
    const full = path.join(dir, name);
    if (!fs.existsSync(full) || !fs.statSync(full).isFile()) {
      throw new Error("pinned runtime is missing " + name);
    }
    const data = fs.readFileSync(full);
    const meta = files[name];
    if (data.length !== meta.size || sha256(full) !== meta.sha256) {
      throw new Error("pinned runtime sha256 mismatch for " + name);
    }
  }
  const lock = JSON.parse(fs.readFileSync(path.join(dir, "pyodide-lock.json"), "utf8"));
  const packages = lock.packages || {};
  const roots = ["numpy", "scipy", "pillow", "micropip"];
  const seen = [];
  const stack = roots.slice();
  while (stack.length) {
    const name = stack.pop();
    if (seen.indexOf(name) >= 0) {
      continue;
    }
    if (!packages[name]) {
      throw new Error("lock file has no package " + name);
    }
    seen.push(name);
    const depends = packages[name].depends || [];
    for (let i = 0; i < depends.length; i++) {
      stack.push(depends[i]);
    }
  }
  for (let i = 0; i < seen.length; i++) {
    const pkg = packages[seen[i]];
    const pin = files[pkg.file_name];
    if (!pin || pin.sha256 !== pkg.sha256) {
      throw new Error("lock sha256 is not the pin for " + pkg.file_name);
    }
  }
  return pins.version;
}

function mountFont(pyodide) {
  const listed = pyodide.runPython(
    "from qbar.plot_static import FONT_CANDIDATES\nlist(FONT_CANDIDATES)\n"
  );
  const paths = Array.from(listed.toJs());
  listed.destroy();
  for (let i = 0; i < paths.length; i++) {
    if (fs.existsSync(paths[i]) && fs.statSync(paths[i]).isFile()) {
      pyodide.FS.mkdirTree(path.dirname(paths[i]));
      pyodide.FS.writeFile(paths[i], new Uint8Array(fs.readFileSync(paths[i])));
      return paths[i];
    }
  }
  return "";
}

function diffJson(left, right, prefix, allowed, unexpected) {
  if (prefix === "git_commit") {
    if (JSON.stringify(left) !== JSON.stringify(right)) {
      allowed.push("git_commit " + JSON.stringify(left) + " vs " + JSON.stringify(right));
    }
    return;
  }
  const leftObject = left && typeof left === "object";
  const rightObject = right && typeof right === "object";
  if (Array.isArray(left) || Array.isArray(right) || !leftObject || !rightObject) {
    if (JSON.stringify(left) !== JSON.stringify(right)) {
      unexpected.push(prefix || "$");
    }
    return;
  }
  const keys = Object.keys(left).concat(Object.keys(right));
  const seen = Object.create(null);
  for (let i = 0; i < keys.length; i++) {
    if (seen[keys[i]]) {
      continue;
    }
    seen[keys[i]] = true;
    if (!Object.prototype.hasOwnProperty.call(left, keys[i]) ||
        !Object.prototype.hasOwnProperty.call(right, keys[i])) {
      unexpected.push((prefix ? prefix + "." : "") + keys[i]);
      continue;
    }
    diffJson(left[keys[i]], right[keys[i]], (prefix ? prefix + "." : "") + keys[i], allowed, unexpected);
  }
}

function replaceAll(text, from, to) {
  return text.split(from).join(to);
}

async function main() {
  const args = parseArgs(process.argv);
  const manifestPath = path.join(args.dist, "manifest.json");
  const manifest = JSON.parse(fs.readFileSync(manifestPath, "utf8"));
  const wheelPath = path.join(args.dist, manifest.wheel);
  const wheelBytes = new Uint8Array(fs.readFileSync(wheelPath));
  const pyDir = path.join(args.out, "py", "run");
  const cliDir = path.join(args.out, "cli", "run");
  prepare(pyDir);
  prepare(cliDir);

  const files = collectFixture(args.fixture, args.kMin, args.kMax);
  const job = {
    files: files.map(function (file) {
      return { role: file.role, name: file.name, bytes: file.bytes };
    }),
    kMin: args.kMin,
    kMax: args.kMax,
    method: args.method,
    vector: args.vector,
    idCol: args.idCol,
    groupCol: args.groupCol,
  };
  const argv = buildJobArgv(job);
  const hostArgv = argv.map(function (token) {
    if (token.indexOf("/in/") === 0) {
      const name = token.slice(4);
      const found = files.filter(function (file) { return file.name === name; })[0];
      if (!found) {
        throw new Error("argv names a file that was not collected");
      }
      return found.hostPath;
    }
    if (token === "/out") {
      return cliDir;
    }
    return token;
  });

  const pinnedVersion = verifyPinnedRuntime(args.pyodide);
  console.log("pinned", pinnedVersion);
  const pyodideUrl = pathToFileURL(path.join(args.pyodide, "pyodide.mjs")).href;
  const imported = await import(pyodideUrl);
  const pyodide = await bootRuntime(imported.loadPyodide, args.pyodide);
  const methods = await installWheel(pyodide, manifest.wheel, wheelBytes, manifest.sha256);
  const font = mountFont(pyodide);
  const versions = pyodide.runPython(
    "import numpy, scipy, PIL, platform, sys\n" +
    "{\n" +
    " 'numpy': numpy.__version__,\n" +
    " 'scipy': scipy.__version__,\n" +
    " 'pillow': PIL.__version__,\n" +
    " 'python': platform.python_version(),\n" +
    " 'hash_randomization': int(sys.flags.hash_randomization),\n" +
    "}\n"
  );
  const pyVersions = versions.toJs({ dict_converter: Object.fromEntries });
  versions.destroy();
  console.log("pyodide", JSON.stringify(pyVersions));
  console.log("methods", methods.join(","));
  console.log("font", font || "(none)");
  console.log("argv", argv.join(" "));

  const result = await runQbar(pyodide, job);
  if (!result.ok) {
    console.error(result.message);
    console.error(result.stderr);
    process.exit(1);
  }
  writeTree(pyDir, result.files);

  const env = Object.assign({}, process.env, {
    PYTHONHASHSEED: "0",
    PYTHONDONTWRITEBYTECODE: "1",
  });
  const cli = spawnSync(args.python, [path.join(repo, "qbar.py")].concat(hostArgv), {
    cwd: repo,
    env: env,
  });
  if (cli.status !== 0) {
    console.error(cli.stderr.toString("utf8"));
    process.exit(cli.status || 1);
  }
  const colour = spawnSync(args.python, ["-c",
    "import sys\n" +
    "from qbar.state import colours_tsv, load_state\n" +
    "text = colours_tsv(load_state(sys.argv[1]))\n" +
    "handle = open(sys.argv[2], 'w', encoding='utf-8', newline='\\n')\n" +
    "handle.write(text)\n" +
    "handle.close()\n",
    path.join(cliDir, "state.json"),
    path.join(cliDir, "colours.tsv"),
  ], { cwd: repo, env: env, encoding: "utf8" });
  if (colour.status !== 0) {
    console.error(colour.stderr);
    process.exit(colour.status || 1);
  }

  const compared = spawnSync(args.python, [
    path.join(repo, "tools", "compare_outputs.py"),
    path.join(args.out, "cli"),
    path.join(args.out, "py"),
  ], { cwd: repo, env: env, encoding: "utf8" });
  process.stdout.write(compared.stdout || "");
  if (compared.stderr) {
    process.stderr.write(compared.stderr);
  }
  const summaryLine = (compared.stdout || "").split("\n").filter(function (line) {
    return line.indexOf("summary ") === 0;
  })[0] || "";
  if (!summaryLine) {
    console.error("compare_outputs.py did not print a summary");
    process.exit(compared.status || 1);
  }
  function summaryCount(name) {
    const match = new RegExp(name + "=(\\d+)").exec(summaryLine);
    return match ? Number(match[1]) : null;
  }
  const differCount = summaryCount("differ");
  const onlyA = summaryCount("only-in-A");
  const onlyB = summaryCount("only-in-B");
  const stderrDiffer = summaryCount("stderr-differ");
  const missingCase = summaryCount("missing-case");
  if (differCount === null || onlyA === null || onlyB === null || stderrDiffer === null || missingCase === null) {
    console.error("compare_outputs.py summary is incomplete");
    process.exit(1);
  }
  const left = listFiles(cliDir);
  const right = listFiles(pyDir);
  const names = Object.keys(left).concat(Object.keys(right)).sort();
  const seen = Object.create(null);
  const unexpected = [];
  const explained = [];
  const figures = [];
  for (let i = 0; i < names.length; i++) {
    const rel = names[i];
    if (seen[rel]) {
      continue;
    }
    seen[rel] = true;
    const ext = path.extname(rel).toLowerCase();
    if (!left[rel] || !right[rel]) {
      if (ext === ".png" || ext === ".pdf") {
        figures.push({
          rel: rel,
          leftPath: left[rel] || null,
          rightPath: right[rel] || null,
          sameBytes: false,
        });
      } else {
        unexpected.push(rel + " missing on one side");
      }
      continue;
    }
    const a = fs.readFileSync(left[rel]);
    const b = fs.readFileSync(right[rel]);
    const sameBytes = a.equals(b);
    if (ext === ".png" || ext === ".pdf") {
      figures.push({
        rel: rel,
        leftPath: left[rel],
        rightPath: right[rel],
        sameBytes: sameBytes,
      });
      continue;
    }
    if (sameBytes) {
      continue;
    }
    if (rel === "state.json") {
      const allowed = [];
      const bad = [];
      diffJson(JSON.parse(a.toString("utf8")), JSON.parse(b.toString("utf8")), "", allowed, bad);
      if (bad.length) {
        unexpected.push("state.json " + bad.join(","));
      } else {
        explained.push("state.json " + (allowed.join("; ") || "identical after parse"));
      }
      continue;
    }
    if (rel === "args.txt") {
      explained.push("args.txt input paths differ (" + sha256(left[rel]).slice(0, 12) + " " + sha256(right[rel]).slice(0, 12) + ")");
      continue;
    }
    if (rel === "editor.html") {
      const blank = function (text) {
        return text.replace(/"git_commit"\s*:\s*"[^"]*"/g, '"git_commit":"COMMIT"');
      };
      if (blank(a.toString("utf8")) === blank(b.toString("utf8"))) {
        explained.push("editor.html differs only by the git_commit field");
      } else {
        unexpected.push("editor.html");
      }
      continue;
    }
    unexpected.push(rel);
  }
  const figuresResult = classifyOutputDiffs(figures, {
    barW: barWidthFromArgv(argv),
    python: args.python,
  });
  for (let i = 0; i < figuresResult.explained.length; i++) {
    explained.push(figuresResult.explained[i]);
  }
  for (let i = 0; i < figuresResult.unexpected.length; i++) {
    unexpected.push(figuresResult.unexpected[i]);
  }
  console.log("explained");
  for (let i = 0; i < explained.length; i++) {
    console.log(explained[i]);
  }
  if (unexpected.length || onlyA || onlyB || stderrDiffer || missingCase || explained.length < differCount) {
    console.log("unexpected");
    for (let i = 0; i < unexpected.length; i++) {
      console.log(unexpected[i]);
    }
    console.log(
      "compare_outputs differ=" + differCount +
      " allow-list=" + explained.length +
      " only-in-A=" + onlyA +
      " only-in-B=" + onlyB +
      " stderr-differ=" + stderrDiffer +
      " missing-case=" + missingCase
    );
    process.exit(1);
  }
  console.log("allow-list covered " + differCount + " compare_outputs differences");
  console.log("cross-check TSV and state fields agree, with the explained files above");
  process.exit(0);
}

if (process.argv[1] && path.resolve(process.argv[1]) === scriptPath) {
  main().catch(function (err) {
    console.error(err && err.stack ? err.stack : err);
    process.exit(1);
  });
}
