import { expect, test } from "@playwright/test";
import { spawn, spawnSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const webRoot = path.resolve(here, "..");
const repo = path.resolve(webRoot, "..");
const port = 4173;
const limit = 209715200;

function packageVersion() {
  const text = fs.readFileSync(path.join(repo, "src", "qbar", "__init__.py"), "utf8");
  const line = text.split("\n").find(function (row) {
    return row.startsWith("__version__");
  });
  if (!line) {
    throw new Error("src/qbar/__init__.py has no __version__");
  }
  return line.split("=")[1].trim().replace(/^['"]|['"]$/g, "");
}

function headCommit() {
  const proc = spawnSync("git", ["-C", repo, "rev-parse", "HEAD"], { encoding: "utf8" });
  if (proc.status !== 0) {
    throw new Error(proc.stderr || "git rev-parse failed");
  }
  return proc.stdout.trim();
}

function pythonBin() {
  if (process.env.QBAR_PYTHON) {
    return process.env.QBAR_PYTHON;
  }
  const local = path.join(repo, ".venv-audit", "bin", "python");
  if (fs.existsSync(local)) {
    return local;
  }
  return "python3";
}

function watchLocalOnly(page) {
  const foreign = [];
  const pending = page.context().route("**/*", async function (route) {
    const url = route.request().url();
    let parsed;
    try {
      parsed = new URL(url);
    } catch (err) {
      foreign.push(url);
      await route.abort();
      return;
    }
    if (parsed.protocol === "blob:" || parsed.protocol === "data:") {
      await route.continue();
      return;
    }
    const same = parsed.hostname === "127.0.0.1" && String(parsed.port) === String(port);
    if (!same) {
      foreign.push(url);
      await route.abort();
      return;
    }
    await route.continue();
  });
  return { foreign: foreign, pending: pending };
}

async function openReady(page) {
  const watch = watchLocalOnly(page);
  await watch.pending;
  const started = Date.now();
  page.on("pageerror", function (err) {
    console.log("pageerror", err && err.message ? err.message : String(err));
  });
  await page.goto("/");
  const status = page.locator("#status");
  await expect(status).toHaveAttribute("data-state", /ready|error/, { timeout: 180000 });
  if ((await status.getAttribute("data-state")) === "error") {
    throw new Error(await page.locator("#error").innerText());
  }
  const version = packageVersion();
  const commit = headCommit();
  const short = commit.slice(0, 12);
  expect(short).toMatch(/^[0-9a-f]{12}$/);
  const info = JSON.parse(fs.readFileSync(path.join(webRoot, "dist", "build-info.json"), "utf8"));
  expect(info.version).toBe(version);
  expect(info.commit).toBe(commit);
  expect(info.display.startsWith("qbar " + version + " (commit " + short + ")")).toBe(true);
  await expect(page.locator("#build-info")).toHaveText(info.display);
  await expect(page.locator("#build-info")).toContainText("qbar " + version + " (commit " + short + ")");
  return { watch: watch, readyMs: Date.now() - started, version: version, commit: commit };
}

test("page reaches ready, shows the version line, and refuses 200 MB", async function ({ page }) {
  test.setTimeout(240000);
  const opened = await openReady(page);
  expect(opened.watch.foreign).toEqual([]);
  console.log("ready_ms", opened.readyMs);

  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "qbar-oversize-"));
  const big = path.join(dir, "big.2.Q");
  const handle = fs.openSync(big, "w");
  try {
    fs.ftruncateSync(handle, limit + 1);
  } finally {
    fs.closeSync(handle);
  }
  const size = fs.statSync(big).size;
  if (size !== limit + 1) {
    console.log("oversize skipped: filesystem reported " + size + " bytes, not 209715201");
  } else {
    await page.locator("#q-files").setInputFiles(big);
    await page.locator("#run").click();
    await expect(page.locator("#error")).toHaveText(
      "These files are " + (limit + 1) + " bytes. The limit is " + limit + " bytes (200 MB)."
    );
    await expect(page.locator("#status")).toHaveAttribute("data-state", "error");
    expect(opened.watch.foreign).toEqual([]);
  }
});

test("a run stays on 127.0.0.1 and matches the command line", async function ({ page }) {
  test.setTimeout(600000);
  const opened = await openReady(page);
  const demo = path.join(repo, "demo", "2448");
  await page.locator("#q-files").setInputFiles([
    path.join(demo, "ref2448_pruned.2.Q"),
    path.join(demo, "ref2448_pruned.3.Q"),
  ]);
  await page.locator("#sample-file").setInputFiles(path.join(demo, "ref2448_pruned.fam"));
  await page.locator("#groups-file").setInputFiles(path.join(demo, "groups.tsv"));
  await page.locator("#id-col").fill("id");
  await page.locator("#group-col").fill("group");
  await expect(page.locator("#k-min")).toHaveValue("2");
  await expect(page.locator("#k-max")).toHaveValue("3");
  const started = Date.now();
  await page.locator("#run").click();
  await expect(page.locator("#status")).toHaveAttribute("data-state", "done", { timeout: 300000 });
  const runMs = Date.now() - started;
  await expect(page.locator("#downloads")).toContainText("order.tsv");
  expect(opened.watch.foreign).toEqual([]);
  console.log("run_ms", runMs);

  const out = fs.mkdtempSync(path.join(os.tmpdir(), "qbar-web-check-"));
  const script = path.join(repo, "tools", "web_check.mjs");
  const args = [
    script,
    "--pyodide", path.join(webRoot, "dist", "pyodide"),
    "--dist", path.join(webRoot, "dist"),
    "--out", out,
    "--python", pythonBin(),
    "--fixture", demo,
    "--k-min", "2",
    "--k-max", "3",
    "--id-col", "id",
    "--group-col", "group",
    "--method", "greedy",
    "--vector", "off",
  ];
  const checkStarted = Date.now();
  const result = await new Promise(function (resolve) {
    const child = spawn(process.execPath, args, { cwd: repo });
    let stdout = "";
    let stderr = "";
    child.stdout.on("data", function (chunk) { stdout += chunk; });
    child.stderr.on("data", function (chunk) { stderr += chunk; });
    child.on("close", function (code) {
      resolve({ code: code, stdout: stdout, stderr: stderr });
    });
  });
  console.log("web_check_ms", Date.now() - checkStarted);
  expect(result.stdout + result.stderr, result.stderr).toContain("allow-list covered");
  expect(result.code).toBe(0);
  expect(opened.watch.foreign).toEqual([]);
});
