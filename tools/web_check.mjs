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
  const pillow = spawnSync(args.python, ["-c", "import PIL; print(PIL.__version__)"], {
    cwd: repo,
    env: env,
    encoding: "utf8",
  });
  if (pillow.status !== 0) {
    console.error(pillow.stderr || "could not read the command-line Pillow version");
    process.exit(pillow.status || 1);
  }
  const cliPillow = pillow.stdout.trim();
  const pyPillow = String(pyVersions.pillow);
  const pdfReason = "PDF bytes differ; Pillow " + pyPillow +
    " in Pyodide and Pillow " + cliPillow + " on the command line";

  const left = listFiles(cliDir);
  const right = listFiles(pyDir);
  const names = Object.keys(left).concat(Object.keys(right)).sort();
  const seen = Object.create(null);
  const unexpected = [];
  const explained = [];
  for (let i = 0; i < names.length; i++) {
    const rel = names[i];
    if (seen[rel]) {
      continue;
    }
    seen[rel] = true;
    if (!left[rel] || !right[rel]) {
      unexpected.push(rel + " missing on one side");
      continue;
    }
    const a = fs.readFileSync(left[rel]);
    const b = fs.readFileSync(right[rel]);
    if (a.equals(b)) {
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
    const ext = path.extname(rel).toLowerCase();
    if (ext === ".png") {
      const pixel = spawnSync(args.python, ["-c",
        "from PIL import Image\n" +
        "import sys\n" +
        "a = Image.open(sys.argv[1])\n" +
        "b = Image.open(sys.argv[2])\n" +
        "same = a.size == b.size and a.mode == b.mode and list(a.getdata()) == list(b.getdata())\n" +
        "print('pixels-identical' if same else 'pixels-differ %s %s %s %s' % (a.size, a.mode, b.size, b.mode))\n",
        left[rel], right[rel],
      ], { encoding: "utf8" });
      const note = pixel.status === 0 ? pixel.stdout.trim() : "pixel-compare-failed";
      if (note === "pixels-identical") {
        explained.push(rel + " bytes differ and pixels match");
      } else {
        unexpected.push(rel + " " + note);
      }
      continue;
    }
    if (ext === ".pdf") {
      if (pyPillow !== cliPillow) {
        explained.push(rel + " " + pdfReason);
      } else {
        unexpected.push(rel + " PDF bytes differ and the Pillow versions match");
      }
      continue;
    }
    unexpected.push(rel);
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

main().catch(function (err) {
  console.error(err && err.stack ? err.stack : err);
  process.exit(1);
});
