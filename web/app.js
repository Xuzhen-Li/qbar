import {
  MAX_INPUT_BYTES,
  equivalentCommand,
  filenameK,
  safeBase,
  sizeMessage,
} from "./page_argv.mjs";

const state = {
  failed: false,
  ready: false,
  running: false,
  qFiles: [],
  sampleFile: null,
  groupsFile: null,
  urls: [],
};

function byId(id) {
  return document.getElementById(id);
}

function setStatus(word) {
  const node = byId("status");
  node.textContent = word;
  node.setAttribute("data-state", word);
}

function setError(text) {
  byId("error").textContent = text || "";
}

function setNotes(text) {
  byId("notes").textContent = text || "";
}

function fail(message) {
  if (state.failed) {
    return;
  }
  state.failed = true;
  state.running = false;
  setStatus("error");
  setError(message);
}

function clearNode(node) {
  while (node.firstChild) {
    node.removeChild(node.firstChild);
  }
}

function revokeUrls() {
  for (let i = 0; i < state.urls.length; i++) {
    URL.revokeObjectURL(state.urls[i]);
  }
  state.urls = [];
}

function remember(url) {
  state.urls.push(url);
  return url;
}

function sampleKind() {
  const chosen = document.querySelector("input[name='sample-kind']:checked");
  return chosen ? chosen.value : "fam";
}

function readBound(id) {
  const input = byId(id);
  if (input.disabled) {
    return null;
  }
  return input.value;
}

function formJob() {
  const files = [];
  for (let i = 0; i < state.qFiles.length; i++) {
    files.push({ role: "q", name: safeBase(state.qFiles[i].name) });
  }
  if (state.sampleFile) {
    files.push({ role: sampleKind(), name: safeBase(state.sampleFile.name) });
  }
  if (state.groupsFile) {
    files.push({ role: "groups", name: safeBase(state.groupsFile.name) });
  }
  return {
    files: files,
    kMin: readBound("k-min"),
    kMax: readBound("k-max"),
    method: byId("method").value,
    vector: byId("vector").value,
    idCol: byId("id-col").value,
    groupCol: byId("group-col").value,
  };
}

function refreshCommand() {
  try {
    byId("command").textContent = equivalentCommand(formJob());
  } catch (err) {
    byId("command").textContent = err && err.message ? err.message : String(err);
  }
}

function refreshFileList() {
  const list = byId("file-list");
  clearNode(list);
  const rows = [];
  for (let i = 0; i < state.qFiles.length; i++) {
    rows.push(["Q", state.qFiles[i]]);
  }
  if (state.sampleFile) {
    rows.push([sampleKind(), state.sampleFile]);
  }
  if (state.groupsFile) {
    rows.push(["groups", state.groupsFile]);
  }
  if (!rows.length) {
    const item = document.createElement("li");
    item.textContent = "No files yet.";
    list.appendChild(item);
    return;
  }
  let total = 0;
  for (let i = 0; i < rows.length; i++) {
    total += rows[i][1].size;
    const item = document.createElement("li");
    item.textContent = rows[i][0] + ": " + rows[i][1].name + " (" + rows[i][1].size + " bytes)";
    list.appendChild(item);
  }
  const sum = document.createElement("li");
  sum.textContent = "Total " + total + " bytes. Limit " + MAX_INPUT_BYTES + " bytes.";
  list.appendChild(sum);
}

function refreshKRange() {
  const ks = [];
  let unlabeled = 0;
  for (let i = 0; i < state.qFiles.length; i++) {
    const k = filenameK(state.qFiles[i].name);
    if (k === null) {
      unlabeled += 1;
    } else if (ks.indexOf(k) < 0) {
      ks.push(k);
    }
  }
  ks.sort(function (a, b) { return a - b; });
  const minInput = byId("k-min");
  const maxInput = byId("k-max");
  const note = byId("k-note");
  if (!ks.length) {
    minInput.disabled = true;
    maxInput.disabled = true;
    minInput.value = "";
    maxInput.value = "";
    note.textContent = unlabeled
      ? "These file names have no K. All of them are used."
      : "K is taken from the file names after you choose Q files.";
    return;
  }
  minInput.disabled = false;
  maxInput.disabled = false;
  minInput.value = String(ks[0]);
  maxInput.value = String(ks[ks.length - 1]);
  note.textContent = "K in these file names: " + ks.join(", ") +
    (unlabeled ? ". Files with no K in the name are always included." : ".");
}

function refreshForm() {
  refreshFileList();
  refreshKRange();
  refreshCommand();
}

function selectedBytes() {
  let total = 0;
  for (let i = 0; i < state.qFiles.length; i++) {
    total += state.qFiles[i].size;
  }
  if (state.sampleFile) {
    total += state.sampleFile.size;
  }
  if (state.groupsFile) {
    total += state.groupsFile.size;
  }
  return total;
}

function readBlob(file) {
  return file.arrayBuffer().then(function (buffer) {
    return {
      role: file._qbarRole,
      name: safeBase(file.name),
      bytes: new Uint8Array(buffer),
    };
  });
}

function fillMethods(methods) {
  const select = byId("method");
  const previous = select.value || "greedy";
  clearNode(select);
  for (let i = 0; i < methods.length; i++) {
    const option = document.createElement("option");
    option.value = methods[i];
    option.textContent = methods[i];
    select.appendChild(option);
  }
  if (previous && Array.prototype.indexOf.call(methods, previous) >= 0) {
    select.value = previous;
  } else if (methods.length) {
    select.value = methods[0];
  }
  select.disabled = false;
}

function showFiles(files, stderr) {
  revokeUrls();
  const figures = byId("figures");
  const downloads = byId("downloads");
  clearNode(figures);
  clearNode(downloads);
  for (let i = 0; i < files.length; i++) {
    const file = files[i];
    const bytes = new Uint8Array(file.bytes);
    const png = file.name.toLowerCase().endsWith(".png");
    const type = png ? "image/png" : "application/octet-stream";
    const url = remember(URL.createObjectURL(new Blob([bytes], { type: type })));
    if (png) {
      const figure = document.createElement("figure");
      const image = document.createElement("img");
      image.alt = "Bar plot " + file.name;
      image.src = url;
      const caption = document.createElement("figcaption");
      caption.textContent = file.name;
      figure.appendChild(image);
      figure.appendChild(caption);
      figures.appendChild(figure);
    }
    const link = document.createElement("a");
    link.href = url;
    link.download = file.name.replace(/\//g, "__");
    link.textContent = file.name;
    const item = document.createElement("li");
    item.appendChild(link);
    downloads.appendChild(item);
  }
  setNotes(stderr || "");
  setError("");
  setStatus("done");
  state.running = false;
}

function startThread() {
  const thread = new Worker("worker.js", { type: "module" });
  thread.onerror = function (event) {
    fail(event.message || "The background thread stopped.");
  };
  thread.onmessage = function (event) {
    const data = event.data || {};
    if (data.type === "ready") {
      if (state.failed) {
        return;
      }
      fillMethods(data.methods || []);
      state.ready = true;
      byId("run").disabled = false;
      setStatus("ready");
      refreshCommand();
      return;
    }
    if (data.type === "error") {
      state.running = false;
      setStatus("error");
      setError(data.message || "qbar stopped.");
      setNotes(data.stderr || "");
      return;
    }
    if (data.type === "done") {
      showFiles(data.files || [], data.stderr || "");
    }
  };
  thread.postMessage({ type: "init" });
  byId("run").addEventListener("click", function () {
    if (!state.ready || state.running || state.failed) {
      return;
    }
    const total = selectedBytes();
    if (total > MAX_INPUT_BYTES) {
      setStatus("error");
      setError(sizeMessage(total));
      return;
    }
    let job;
    try {
      job = formJob();
      equivalentCommand(job);
    } catch (err) {
      setStatus("error");
      setError(err && err.message ? err.message : String(err));
      return;
    }
    const pending = [];
    for (let i = 0; i < state.qFiles.length; i++) {
      state.qFiles[i]._qbarRole = "q";
      pending.push(readBlob(state.qFiles[i]));
    }
    if (state.sampleFile) {
      state.sampleFile._qbarRole = sampleKind();
      pending.push(readBlob(state.sampleFile));
    }
    if (state.groupsFile) {
      state.groupsFile._qbarRole = "groups";
      pending.push(readBlob(state.groupsFile));
    }
    state.running = true;
    setStatus("running");
    setError("");
    setNotes("");
    Promise.all(pending).then(function (files) {
      const transfer = [];
      const payload = [];
      for (let i = 0; i < files.length; i++) {
        payload.push({
          role: files[i].role,
          name: files[i].name,
          bytes: files[i].bytes.buffer,
        });
        transfer.push(files[i].bytes.buffer);
      }
      thread.postMessage({
        type: "run",
        files: payload,
        kMin: job.kMin,
        kMax: job.kMax,
        method: job.method,
        vector: job.vector,
        idCol: job.idCol,
        groupCol: job.groupCol,
      }, transfer);
    }).catch(function (err) {
      state.running = false;
      setStatus("error");
      setError(err && err.message ? err.message : String(err));
    });
  });
}

function bindFiles() {
  byId("q-files").addEventListener("change", function (event) {
    state.qFiles = Array.prototype.slice.call(event.target.files || []);
    refreshForm();
  });
  const zone = byId("q-drop");
  zone.addEventListener("dragover", function (event) {
    event.preventDefault();
  });
  zone.addEventListener("drop", function (event) {
    event.preventDefault();
    const dropped = Array.prototype.slice.call(event.dataTransfer.files || []);
    for (let i = 0; i < dropped.length; i++) {
      state.qFiles.push(dropped[i]);
    }
    refreshForm();
  });
  byId("q-clear").addEventListener("click", function () {
    state.qFiles = [];
    byId("q-files").value = "";
    refreshForm();
  });
  byId("sample-file").addEventListener("change", function (event) {
    const files = event.target.files || [];
    state.sampleFile = files.length ? files[0] : null;
    refreshForm();
  });
  const radios = document.querySelectorAll("input[name='sample-kind']");
  for (let i = 0; i < radios.length; i++) {
    radios[i].addEventListener("change", refreshForm);
  }
  byId("groups-file").addEventListener("change", function (event) {
    const files = event.target.files || [];
    state.groupsFile = files.length ? files[0] : null;
    refreshForm();
  });
  const watched = ["k-min", "k-max", "method", "vector", "id-col", "group-col"];
  for (let i = 0; i < watched.length; i++) {
    byId(watched[i]).addEventListener("input", refreshCommand);
    byId(watched[i]).addEventListener("change", refreshCommand);
  }
}

bindFiles();
refreshForm();
setStatus("loading");
startThread();
