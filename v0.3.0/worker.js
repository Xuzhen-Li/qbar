// Pyodide runs in this module worker so the page stays responsive.
// Pyodide 314 rejects a classic worker. The page calls qbar.api.run,
// which is the entry the architecture note names. build_parser supplies
// the namespace. cli.main is not used.

import { MAX_INPUT_BYTES, buildJobArgv, sizeMessage } from "./page_argv.mjs";

export const PYODIDE_PACKAGES = ["numpy", "scipy", "pillow", "micropip"];

const WHEEL_NAME = /^[A-Za-z0-9._+-]+\.whl$/;

const RUN_PY = [
  "import io",
  "import os",
  "import sys",
  "import traceback",
  "buf_out = io.StringIO()",
  "buf_err = io.StringIO()",
  "old_out = sys.stdout",
  "old_err = sys.stderr",
  "sys.stdout = buf_out",
  "sys.stderr = buf_err",
  "code = 0",
  "message = ''",
  "try:",
  "    argv = [str(item) for item in qbar_argv]",
  "    from qbar.cli import build_parser",
  "    from qbar.api import run",
  "    args = build_parser('en').parse_args(argv)",
  "    run(args, argv)",
  "    state_path = '/out/state.json'",
  "    if os.path.isfile(state_path):",
  "        from qbar.state import colours_tsv, load_state",
  "        text = colours_tsv(load_state(state_path))",
  "        handle = open('/out/colours.tsv', 'w', encoding='utf-8', newline='\\n')",
  "        try:",
  "            handle.write(text)",
  "        finally:",
  "            handle.close()",
  "except SystemExit as exc:",
  "    status = exc.code",
  "    if status is None or status == 0:",
  "        code = 0",
  "        message = ''",
  "    elif isinstance(status, int):",
  "        code = int(status)",
  "        message = buf_err.getvalue().strip() or ('qbar exited %s' % status)",
  "    else:",
  "        code = 1",
  "        message = str(status)",
  "except Exception:",
  "    code = 1",
  "    message = traceback.format_exc()",
  "finally:",
  "    sys.stdout = old_out",
  "    sys.stderr = old_err",
  "result = {",
  "    'code': code,",
  "    'message': message,",
  "    'stdout': buf_out.getvalue(),",
  "    'stderr': buf_err.getvalue(),",
  "}",
  "result",
].join("\n");

export async function sha256Hex(bytes) {
  const view = bytes instanceof Uint8Array ? bytes : new Uint8Array(bytes);
  const copy = view.buffer.slice(view.byteOffset, view.byteOffset + view.byteLength);
  const digest = await crypto.subtle.digest("SHA-256", copy);
  const out = new Uint8Array(digest);
  let hex = "";
  for (let i = 0; i < out.length; i++) {
    hex += out[i].toString(16).padStart(2, "0");
  }
  return hex;
}

// Same-origin directory that holds the pinned runtime. import.meta.url is
// this file, so the directory is dist/pyodide next to the page.
export function runtimeIndexURL() {
  return new URL("./dist/pyodide/", import.meta.url).href;
}

export async function bootRuntime(loadPyodide, indexURL) {
  // Pyodide 314.0.7 loadPyodide has no checkIntegrity option.
  // loadPackage checkIntegrity defaults to true and checks each lock-file
  // package sha256. Pass true so a later edit cannot turn the check off
  // by relying on the default.
  const pyodide = await loadPyodide({
    indexURL: indexURL,
    env: { PYTHONHASHSEED: "0" },
  });
  await pyodide.loadPackage(PYODIDE_PACKAGES, { checkIntegrity: true });
  return pyodide;
}

export async function installWheel(pyodide, wheelName, wheelBytes, expectedSha256) {
  if (!WHEEL_NAME.test(wheelName)) {
    throw new Error("Manifest wheel name is not a single file name.");
  }
  const hash = await sha256Hex(wheelBytes);
  if (hash !== String(expectedSha256).toLowerCase()) {
    throw new Error("Wheel sha256 does not match the manifest.");
  }
  const bytes = wheelBytes instanceof Uint8Array ? wheelBytes : new Uint8Array(wheelBytes);
  pyodide.FS.mkdirTree("/tmp");
  const wheelPath = "/tmp/" + wheelName;
  pyodide.FS.writeFile(wheelPath, bytes);
  const listed = await pyodide.runPythonAsync(
    "import micropip\n" +
    "await micropip.install(" + JSON.stringify("emfs:" + wheelPath) + ", deps=False)\n" +
    "from qbar.align import ALIGN_METHODS\n" +
    "list(ALIGN_METHODS)\n"
  );
  const methods = Array.from(listed.toJs());
  listed.destroy();
  return methods;
}

function rmTree(pyodide, target) {
  let stat;
  try {
    stat = pyodide.FS.stat(target);
  } catch (err) {
    return;
  }
  if (pyodide.FS.isDir(stat.mode)) {
    const names = pyodide.FS.readdir(target);
    for (let i = 0; i < names.length; i++) {
      if (names[i] === "." || names[i] === "..") {
        continue;
      }
      rmTree(pyodide, target + "/" + names[i]);
    }
    try {
      pyodide.FS.rmdir(target);
    } catch (err) {
      // Leave a directory the filesystem will not remove.
    }
    return;
  }
  pyodide.FS.unlink(target);
}

function readOut(pyodide, dir, prefix) {
  const found = [];
  let names;
  try {
    names = pyodide.FS.readdir(dir);
  } catch (err) {
    return found;
  }
  for (let i = 0; i < names.length; i++) {
    const name = names[i];
    if (name === "." || name === "..") {
      continue;
    }
    const full = dir + "/" + name;
    const rel = prefix ? prefix + "/" + name : name;
    const stat = pyodide.FS.stat(full);
    if (pyodide.FS.isDir(stat.mode)) {
      const nested = readOut(pyodide, full, rel);
      for (let j = 0; j < nested.length; j++) {
        found.push(nested[j]);
      }
    } else {
      const data = pyodide.FS.readFile(full);
      const copy = new Uint8Array(data.byteLength);
      copy.set(data);
      found.push({ name: rel, bytes: copy });
    }
  }
  return found;
}

function asObject(proxy) {
  const value = proxy.toJs({ dict_converter: Object.fromEntries });
  proxy.destroy();
  return value;
}

export async function runQbar(pyodide, job) {
  let total = 0;
  for (let i = 0; i < job.files.length; i++) {
    total += job.files[i].bytes.byteLength;
  }
  if (total > MAX_INPUT_BYTES) {
    return { ok: false, message: sizeMessage(total), stdout: "", stderr: "", files: [] };
  }
  let argv;
  try {
    argv = buildJobArgv(job);
  } catch (err) {
    return {
      ok: false,
      message: err && err.message ? err.message : String(err),
      stdout: "",
      stderr: "",
      files: [],
    };
  }
  rmTree(pyodide, "/in");
  rmTree(pyodide, "/out");
  pyodide.FS.mkdirTree("/in");
  pyodide.FS.mkdirTree("/out");
  for (let i = 0; i < job.files.length; i++) {
    const file = job.files[i];
    const base = file.name;
    const bytes = file.bytes instanceof Uint8Array ? file.bytes : new Uint8Array(file.bytes);
    pyodide.FS.writeFile("/in/" + base, bytes);
  }
  pyodide.globals.set("qbar_argv", argv);
  const proxy = await pyodide.runPythonAsync(RUN_PY);
  const info = asObject(proxy);
  const code = Number(info.code);
  if (code !== 0) {
    return {
      ok: false,
      message: String(info.message || ""),
      stdout: String(info.stdout || ""),
      stderr: String(info.stderr || ""),
      files: [],
    };
  }
  return {
    ok: true,
    message: "",
    stdout: String(info.stdout || ""),
    stderr: String(info.stderr || ""),
    files: readOut(pyodide, "/out", ""),
  };
}

function errorText(err) {
  if (err && err.message) {
    return String(err.message);
  }
  return String(err);
}

async function onInit() {
  const indexURL = runtimeIndexURL();
  const runtimeURL = new URL("pyodide.mjs", indexURL);
  const manifestURL = new URL("../manifest.json", indexURL);
  const imported = await import(runtimeURL.href);
  const pyodide = await bootRuntime(imported.loadPyodide, indexURL);
  const manifestResponse = await fetch(manifestURL);
  if (!manifestResponse.ok) {
    throw new Error("Could not read the wheel manifest. Build the wheel, then reload this page.");
  }
  const manifest = await manifestResponse.json();
  if (!manifest || typeof manifest.wheel !== "string" || typeof manifest.sha256 !== "string") {
    throw new Error("The wheel manifest needs a wheel name and a sha256.");
  }
  if (!WHEEL_NAME.test(manifest.wheel)) {
    throw new Error("Manifest wheel name is not a single file name.");
  }
  const wheelResponse = await fetch(new URL(manifest.wheel, manifestURL));
  if (!wheelResponse.ok) {
    throw new Error("Could not read the local wheel named in the manifest.");
  }
  const wheelBytes = new Uint8Array(await wheelResponse.arrayBuffer());
  const methods = await installWheel(pyodide, manifest.wheel, wheelBytes, manifest.sha256);
  self._pyodide = pyodide;
  self.postMessage({ type: "ready", methods: methods });
}

async function onRun(data) {
  if (!self._pyodide) {
    throw new Error("The runtime is not ready.");
  }
  const files = [];
  for (let i = 0; i < data.files.length; i++) {
    const item = data.files[i];
    files.push({
      role: item.role,
      name: item.name,
      bytes: item.bytes instanceof Uint8Array ? item.bytes : new Uint8Array(item.bytes),
    });
  }
  const result = await runQbar(self._pyodide, {
    files: files,
    kMin: data.kMin,
    kMax: data.kMax,
    method: data.method,
    vector: data.vector,
    idCol: data.idCol,
    groupCol: data.groupCol,
  });
  if (!result.ok) {
    self.postMessage({
      type: "error",
      message: result.message || "qbar stopped.",
      stderr: result.stderr,
    });
    return;
  }
  const payload = [];
  const transfer = [];
  for (let i = 0; i < result.files.length; i++) {
    const file = result.files[i];
    payload.push({ name: file.name, bytes: file.bytes.buffer });
    transfer.push(file.bytes.buffer);
  }
  self.postMessage({
    type: "done",
    files: payload,
    stderr: result.stderr,
  }, transfer);
}

function inWorker() {
  return typeof WorkerGlobalScope !== "undefined" &&
    typeof self !== "undefined" &&
    self instanceof WorkerGlobalScope;
}

if (inWorker()) {
  self.onmessage = function (event) {
    const data = event.data || {};
    const task = data.type === "init" ? onInit(data) : data.type === "run" ? onRun(data) : null;
    if (!task) {
      return;
    }
    task.catch(function (err) {
      self.postMessage({ type: "error", message: errorText(err), stderr: "" });
    });
  };
}
