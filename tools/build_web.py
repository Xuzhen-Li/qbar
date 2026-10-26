#!/usr/bin/env python3
"""Build a qbar wheel and the local Pyodide runtime for the static page.

Usage:
    python tools/build_web.py [OUTDIR]
    python tools/build_web.py --offline [OUTDIR]

The default OUTDIR is web/dist in this repository. The wheel is built with
``pip wheel --no-deps``. Project dependencies are not fetched into the wheel.
The page loads numpy, scipy, and pillow from the pinned Pyodide build and
installs this wheel with dependencies turned off.

``--offline`` adds ``--no-index`` and ``--no-build-isolation`` for the wheel.
It does not use the network. It needs a build backend that is already
installed. Pyodide files are not downloaded. Each file that is already in
OUTDIR/pyodide is checked against web/pyodide-pins.json. A missing file makes
this command exit 3 after the wheel manifest and build-info.json are written. A file that is
present and does not match is left in place and the command exits 1.

A normal run downloads any missing pinned file from the source URL in
web/pyodide-pins.json. The bytes are written to a temporary name in
OUTDIR/pyodide, checked, and renamed to the final file name. A download that
does not match the pin is not given that final name. A file that is already
present and does not match is left in place. A later run that finds every
pinned file already matching downloads nothing.

The script writes OUTDIR/manifest.json and OUTDIR/build-info.json. A later
run replaces that manifest, that build-info file, and a wheel file of the
same name. It does not delete other files. If more than one qbar_plot wheel
is already in OUTDIR, the script stops and names them.

build-info.json records the version from src/qbar/__init__.py, the full
SHA from ``git rev-parse HEAD``, and dirty true when ``git status
--porcelain`` is not empty. The display line is ``qbar <version> (commit
<12-char sha>)``, with `` dirty`` added when dirty is true.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import urllib.request


RUNTIME_FILES = (
    "pyodide.mjs",
    "pyodide.asm.mjs",
    "pyodide.asm.wasm",
    "python_stdlib.zip",
    "pyodide-lock.json",
)
PACKAGE_ROOTS = ("numpy", "scipy", "pillow", "micropip")
OFFLINE_MISSING = 3


def repo_root():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(blob):
    return hashlib.sha256(blob).hexdigest()


def load_pins(root):
    path = os.path.join(root, "web", "pyodide-pins.json")
    with open(path, encoding="utf-8") as handle:
        pins = json.load(handle)
    if pins.get("version") != "314.0.7":
        print("web/pyodide-pins.json version is not 314.0.7", file=sys.stderr)
        return None
    source = pins.get("source") or ""
    files = pins.get("files") or {}
    if not source.endswith("/") or not isinstance(files, dict):
        print("web/pyodide-pins.json needs a source URL and a files object", file=sys.stderr)
        return None
    for name in RUNTIME_FILES:
        meta = files.get(name)
        if not isinstance(meta, dict) or "sha256" not in meta or "size" not in meta:
            print("web/pyodide-pins.json is missing %s" % name, file=sys.stderr)
            return None
    return pins


def file_matches(path, sha, size):
    if not os.path.isfile(path):
        return False
    if os.path.getsize(path) != int(size):
        return False
    return sha256_file(path) == sha


def write_verified(dest_dir, name, blob, sha, size):
    if len(blob) != int(size) or sha256_bytes(blob) != sha:
        print("download does not match the pin for %s" % name, file=sys.stderr)
        return False
    fd, tmp = tempfile.mkstemp(prefix="." + name + ".", suffix=".partial", dir=dest_dir)
    os.close(fd)
    try:
        with open(tmp, "wb") as handle:
            handle.write(blob)
        if not file_matches(tmp, sha, size):
            print("temp copy does not match the pin for %s" % name, file=sys.stderr)
            return False
        final = os.path.join(dest_dir, name)
        if os.path.exists(final):
            print("pinned path appeared during download and was left in place: %s" % name, file=sys.stderr)
            return False
        os.replace(tmp, final)
        tmp = ""
    finally:
        if tmp and os.path.exists(tmp):
            os.remove(tmp)
    return True


def download(url):
    request = urllib.request.Request(url, headers={"User-Agent": "qbar-build-web"})
    with urllib.request.urlopen(request, timeout=180) as response:
        return response.read()


def package_closure(packages):
    seen = []
    stack = list(PACKAGE_ROOTS)
    while stack:
        name = stack.pop()
        if name in seen:
            continue
        if name not in packages:
            print("pyodide-lock.json has no package %s" % name, file=sys.stderr)
            return None
        seen.append(name)
        for dep in packages[name].get("depends") or []:
            stack.append(dep)
    return seen


def check_lock(dest_dir, pins):
    lock_path = os.path.join(dest_dir, "pyodide-lock.json")
    with open(lock_path, encoding="utf-8") as handle:
        lock = json.load(handle)
    packages = lock.get("packages") or {}
    needed = package_closure(packages)
    if needed is None:
        return False
    files = pins["files"]
    for name in needed:
        pkg = packages[name]
        fname = pkg.get("file_name") or ""
        if not fname or "/" in fname or "\\" in fname or ":" in fname:
            print("lock file_name is not a bare file for %s" % name, file=sys.stderr)
            return False
        pin = files.get(fname)
        if not isinstance(pin, dict):
            print("lock file requires %s and that file is not in web/pyodide-pins.json" % fname, file=sys.stderr)
            return False
        if pin.get("sha256") != pkg.get("sha256"):
            print("pin sha256 does not match pyodide-lock.json for %s" % fname, file=sys.stderr)
            return False
        final = os.path.join(dest_dir, fname)
        if not file_matches(final, pin["sha256"], pin["size"]):
            print("installed %s does not match the lock sha256" % fname, file=sys.stderr)
            return False
    return True


def install_pyodide(root, outdir, offline):
    pins = load_pins(root)
    if pins is None:
        return 1
    dest = os.path.join(outdir, "pyodide")
    os.makedirs(dest, exist_ok=True)
    downloaded = 0
    downloaded_bytes = 0
    kept = 0
    missing = []
    source = pins["source"]
    for name in sorted(pins["files"]):
        meta = pins["files"][name]
        sha = str(meta["sha256"])
        size = int(meta["size"])
        final = os.path.join(dest, name)
        if os.path.lexists(final):
            if file_matches(final, sha, size):
                kept += 1
                continue
            actual = sha256_file(final) if os.path.isfile(final) else "not-a-file"
            actual_size = os.path.getsize(final) if os.path.isfile(final) else 0
            print(
                "%s does not match web/pyodide-pins.json "
                "(found sha256 %s size %s, pin sha256 %s size %s). "
                "The file was left in place."
                % (name, actual, actual_size, sha, size),
                file=sys.stderr,
            )
            return 1
        if offline:
            missing.append(name)
            continue
        blob = download(source + name)
        if not write_verified(dest, name, blob, sha, size):
            return 1
        downloaded += 1
        downloaded_bytes += len(blob)
    if missing:
        print("pyodide offline missing: %s" % " ".join(missing), file=sys.stderr)
        print(
            "pyodide downloaded_files=0 downloaded_bytes=0 kept_files=%d" % kept
        )
        return OFFLINE_MISSING
    if not check_lock(dest, pins):
        return 1
    print(
        "pyodide downloaded_files=%d downloaded_bytes=%d kept_files=%d"
        % (downloaded, downloaded_bytes, kept)
    )
    return 0


def read_version(root):
    path = os.path.join(root, "src", "qbar", "__init__.py")
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            if line.startswith("__version__"):
                parts = line.split("=", 1)
                if len(parts) == 2:
                    return parts[1].strip().strip("\"'")
    print("src/qbar/__init__.py has no __version__", file=sys.stderr)
    return None


def git_commit_and_dirty(root):
    """Return (full SHA or unknown, dirty)."""
    rev = subprocess.run(
        ["git", "-C", root, "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    status = subprocess.run(
        ["git", "-C", root, "status", "--porcelain"],
        capture_output=True,
        text=True,
        check=False,
    )
    if rev.returncode != 0 or status.returncode != 0:
        return "unknown", True
    commit = rev.stdout.strip()
    if len(commit) != 40 or any(ch not in "0123456789abcdef" for ch in commit):
        return "unknown", True
    return commit, bool(status.stdout.strip())


def display_line(version, commit, dirty):
    short = commit if len(commit) < 12 else commit[:12]
    text = "qbar %s (commit %s)" % (version, short)
    if dirty:
        text += " dirty"
    return text


def write_build_info(root, outdir):
    """Write OUTDIR/build-info.json. Return the object, or None on failure."""
    version = read_version(root)
    if not version:
        return None
    commit, dirty = git_commit_and_dirty(root)
    payload = {
        "version": version,
        "commit": commit,
        "dirty": dirty,
        "display": display_line(version, commit, dirty),
    }
    os.makedirs(outdir, exist_ok=True)
    path = os.path.join(outdir, "build-info.json")
    text = json.dumps(payload, indent=2) + "\n"
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    shown = path
    if shown.startswith(root + os.sep):
        shown = os.path.relpath(shown, root)
    print(shown)
    return payload


def build_wheel(root, outdir, offline):
    os.makedirs(outdir, exist_ok=True)
    before = set(os.listdir(outdir))
    cmd = [
        sys.executable, "-m", "pip", "wheel", "--no-deps",
        "--disable-pip-version-check", "--wheel-dir", outdir,
    ]
    if offline:
        cmd.extend(["--no-index", "--no-build-isolation"])
    cmd.append(root)
    proc = subprocess.run(cmd)
    if proc.returncode != 0:
        return proc.returncode
    wheels = []
    for name in sorted(os.listdir(outdir)):
        if name.startswith("qbar_plot-") and name.endswith(".whl"):
            wheels.append(name)
    if not wheels:
        print("pip wheel wrote no qbar_plot wheel in the output directory", file=sys.stderr)
        return 1
    if len(wheels) > 1:
        created = [name for name in wheels if name not in before]
        if len(created) == 1:
            wheels = created
        else:
            print("OUTDIR has more than one qbar_plot wheel. This script will not delete them:", file=sys.stderr)
            for name in wheels:
                print(name, file=sys.stderr)
            return 1
    name = wheels[0]
    digest = sha256_file(os.path.join(outdir, name))
    text = json.dumps({"wheel": name, "sha256": digest}, indent=2) + "\n"
    manifest = os.path.join(outdir, "manifest.json")
    with open(manifest, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    shown = manifest
    if shown.startswith(root + os.sep):
        shown = os.path.relpath(shown, root)
    print(shown)
    print(name)
    print(digest)
    return 0


def main(argv):
    offline = False
    args = []
    for item in argv[1:]:
        if item == "--offline":
            offline = True
        elif item == "--help":
            print(__doc__.strip())
            return 0
        else:
            args.append(item)
    if len(args) > 1:
        print("usage: python tools/build_web.py [--offline] [OUTDIR]", file=sys.stderr)
        return 2
    root = repo_root()
    outdir = args[0] if args else os.path.join(root, "web", "dist")
    if not os.path.isabs(outdir):
        outdir = os.path.join(os.getcwd(), outdir)
    wheel_code = build_wheel(root, outdir, offline)
    if wheel_code != 0:
        return wheel_code
    if write_build_info(root, outdir) is None:
        return 1
    return install_pyodide(root, outdir, offline)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
