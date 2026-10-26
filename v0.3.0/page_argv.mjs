// Arguments the page sends to qbar. The check script imports this module
// so it builds the same list.

export const MAX_INPUT_BYTES = 200 * 1024 * 1024;
export const DEFAULT_ID_COL = "analysis_IID";
export const DEFAULT_GROUP_COL = "Dong_Grp";

export function sizeMessage(total) {
  return (
    "These files are " + total +
    " bytes. The limit is " + MAX_INPUT_BYTES +
    " bytes (200 MB)."
  );
}

export function baseName(name) {
  const text = String(name);
  const slash = Math.max(text.lastIndexOf("/"), text.lastIndexOf("\\"));
  return slash >= 0 ? text.slice(slash + 1) : text;
}

export function safeBase(name) {
  const base = baseName(name);
  if (!base || base === "." || base === ".." || base.indexOf("/") >= 0 || base.indexOf("\\") >= 0) {
    throw new Error("A file name must be a single base name.");
  }
  return base;
}

// Same rule as qbar.io.k_of: the digit token immediately before the extension.
export function filenameK(name) {
  const base = baseName(name);
  const dot = base.lastIndexOf(".");
  if (dot <= 0) {
    return null;
  }
  const stem = base.slice(0, dot);
  const cut = stem.lastIndexOf(".");
  if (cut < 0) {
    return null;
  }
  const tail = stem.slice(cut + 1);
  if (!/^[0-9]+$/.test(tail)) {
    return null;
  }
  const value = Number(tail);
  if (!Number.isSafeInteger(value)) {
    return null;
  }
  return value;
}

function columnName(value, fallback) {
  const text = String(value == null ? "" : value).trim();
  return text || fallback;
}

export function requireKBound(value) {
  if (typeof value === "number") {
    if (!Number.isInteger(value) || value < 0) {
      throw new Error("Enter an integer for K from and K to.");
    }
    return value;
  }
  const text = String(value == null ? "" : value).trim();
  if (!/^[0-9]+$/.test(text)) {
    throw new Error("Enter an integer for K from and K to.");
  }
  const parsed = Number(text);
  if (!Number.isSafeInteger(parsed)) {
    throw new Error("Enter an integer for K from and K to.");
  }
  return parsed;
}

export function qFilesForJob(job) {
  const all = job.files.filter(function (file) {
    return file.role === "q";
  });
  if (!all.length) {
    throw new Error("Choose at least one Q file.");
  }
  const named = all.some(function (file) {
    return filenameK(file.name) !== null;
  });
  // File names with no K have nothing to bound. A blank bound is an error
  // once any file name includes a K. It does not mean every file.
  if (!named) {
    return all;
  }
  const lo = requireKBound(job.kMin);
  const hi = requireKBound(job.kMax);
  if (lo > hi) {
    throw new Error("The K range is not usable.");
  }
  const chosen = all.filter(function (file) {
    const k = filenameK(file.name);
    if (k === null) {
      return true;
    }
    return k >= lo && k <= hi;
  });
  if (!chosen.length) {
    throw new Error("No Q file is inside that K range.");
  }
  return chosen;
}

export function buildJobArgv(job) {
  const seen = Object.create(null);
  for (let i = 0; i < job.files.length; i++) {
    const base = safeBase(job.files[i].name);
    if (seen[base]) {
      throw new Error("Two files use the name " + base + ".");
    }
    seen[base] = true;
  }
  const qFiles = qFilesForJob(job);
  const argv = ["--q"];
  for (let i = 0; i < qFiles.length; i++) {
    argv.push("/in/" + safeBase(qFiles[i].name));
  }
  const fam = job.files.filter(function (file) { return file.role === "fam"; });
  const ids = job.files.filter(function (file) { return file.role === "ids"; });
  if (fam.length > 1 || ids.length > 1 || (fam.length && ids.length)) {
    throw new Error("Choose fam or ids, not both.");
  }
  if (fam.length) {
    argv.push("--fam", "/in/" + safeBase(fam[0].name));
  }
  if (ids.length) {
    argv.push("--ids", "/in/" + safeBase(ids[0].name));
  }
  const groups = job.files.filter(function (file) { return file.role === "groups"; });
  if (groups.length > 1) {
    throw new Error("Choose one groups file.");
  }
  if (groups.length) {
    argv.push("--groups", "/in/" + safeBase(groups[0].name));
    argv.push("--id-col", columnName(job.idCol, DEFAULT_ID_COL));
    argv.push("--group-col", columnName(job.groupCol, DEFAULT_GROUP_COL));
  }
  if (job.method) {
    argv.push("--align-method", String(job.method));
  }
  const vector = job.vector || "off";
  if (vector !== "off") {
    if (vector !== "pdf" && vector !== "svg" && vector !== "both") {
      throw new Error("Vector choice is not off, pdf, svg, or both.");
    }
    argv.push("--vector", vector);
  }
  // state.json is written only when --editor is on. The replay command
  // drops this flag and passes --state instead.
  argv.push("--editor", "--outdir", "/out");
  return argv;
}

export function shellQuote(token) {
  return "'" + String(token).replace(/'/g, "'\\''") + "'";
}

export function equivalentCommand(job) {
  const argv = buildJobArgv(job);
  const args = [];
  for (let i = 0; i < argv.length; i++) {
    const token = argv[i];
    if (token === "--editor") {
      continue;
    }
    if (token === "--outdir") {
      i += 1;
      continue;
    }
    if (token.indexOf("/in/") === 0) {
      args.push(token.slice(4));
    } else {
      args.push(token);
    }
  }
  args.push("--state", "state.json", "--outdir", "out");
  return "qbar " + args.map(shellQuote).join(" ");
}
