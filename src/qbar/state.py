"""Replayable run state.

The file schema is ``qbar-state``, ``schema_version`` 1. Each input is
stored as a base name and a SHA256 of the file bytes. The directory is
not stored. ``--state`` matches those records to the files on the command
line by role and by order within that role.

Roles are ``q`` (matrix files, in the order they were collected), then
``fam``, ``ids``, or ``ind`` for the one sample-id source, then
``groups`` when a groups file was given.

``sample_order`` is the display order, one iid per entry.
``group_order`` must be the order in which those groups first appear in
``sample_order``. ``sample_groups`` is parallel to ``sample_order`` and is
checked against the groups file when it is present. The editor uses it to
keep a move inside one group.

``swaps`` maps each K to a permutation. Display column ``i`` is aligned
column ``swaps[i]`` before the swap is applied. ``alignment_overridden``
is true after a swap. A non-identity permutation with the flag false is
an error.

``clusters`` lists ``name`` and ``colour`` in display order for each K.
``colour`` is checked with ``norm_hex``. Column 0 is the bottom of the
stack.

``k`` and ``align_method`` must match the command. ``plot`` records other
options used to build the figure. Replay does not read ``plot``.

``colours.tsv`` is one cluster per line, low K to high K, bottom column
to top. Each line is the name, a tab, and ``#rrggbb``. ``parse_colors``
splits on whitespace and joins ``name=#rrggbb``. A name that is ``C`` or
``c`` plus digits is a column colour. Any other name is a group colour.
The same name can occur once per K; the last line wins in ``parse_colors``.
Per-K colours stay in this JSON file. ``order.txt`` is one iid per line.
"""
from __future__ import annotations

import hashlib
import json
import os

import numpy as np

from .io import norm_hex
from .messages import text as _msg
from .order import spans_of

SCHEMA = "qbar-state"
SCHEMA_VERSION = 1


def _exit(key, language, **values):
    raise SystemExit(_msg(key, language, **values))


def file_sha256(path):
    """SHA256 hex digest of the bytes in ``path``."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def command_inputs(q_paths, fam=None, ids_path=None, ind=None, groups=None):
    """Input records in replay order.

    Each record has ``role``, ``path`` (as given), ``name`` (base name),
    and ``sha256``.
    """
    rows = []
    for path in q_paths:
        rows.append(_record("q", path))
    if fam:
        rows.append(_record("fam", fam))
    elif ids_path:
        rows.append(_record("ids", ids_path))
    elif ind:
        rows.append(_record("ind", ind))
    if groups:
        rows.append(_record("groups", groups))
    return rows


def _record(role, path):
    return {
        "role": role,
        "path": path,
        "name": os.path.basename(path),
        "sha256": file_sha256(path),
    }


def load_state(path, *, language="en"):
    """Read a state file and require schema ``qbar-state`` version 1."""
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except OSError:
        _exit("state_open", language, path=path)
    except json.JSONDecodeError:
        _exit("state_json", language, path=path)
    if not isinstance(data, dict):
        _exit("state_json", language, path=path)
    schema = data.get("schema")
    if schema != SCHEMA:
        _exit("state_schema", language, schema=schema)
    version = data.get("schema_version")
    if type(version) is not int or version != SCHEMA_VERSION:
        _exit("state_version", language, version=version)
    return data


def check_state_inputs(state, records, *, language="en"):
    """Match recorded SHA256 values to command-line files by role and order.

    A count mismatch or a hash mismatch names the command-line path.
    """
    inputs = state.get("inputs")
    if not isinstance(inputs, list):
        _exit("state_missing", language, field="inputs")
    cli = {}
    order = []
    for rec in records:
        role = rec["role"]
        if role not in cli:
            cli[role] = []
            order.append(role)
        cli[role].append(rec)
    got = {}
    for item in inputs:
        if not isinstance(item, dict) or "role" not in item:
            _exit("state_missing", language, field="inputs.role")
        role = item["role"]
        if role not in got:
            got[role] = []
            if role not in cli:
                order.append(role)
        got[role].append(item)
    for role in order:
        left = cli.get(role, [])
        right = got.get(role, [])
        if len(left) != len(right):
            if left:
                shown = ", ".join(item["path"] for item in left)
            else:
                shown = "(none)"
            _exit(
                "state_count",
                language,
                role=role,
                state_n=len(right),
                cli_n=len(left),
                path=shown,
            )
        for rec, item in zip(left, right):
            digest = file_sha256(rec["path"])
            if item.get("sha256") != digest:
                _exit("state_hash", language, path=rec["path"])


def _as_int_list(values):
    return [int(item) for item in values]


def _join(values):
    return ", ".join(str(item) for item in values)


def _permutation(raw, k):
    if not isinstance(raw, list) or len(raw) != k:
        return None
    try:
        perm = [int(item) for item in raw]
    except (TypeError, ValueError):
        return None
    if sorted(perm) != list(range(k)):
        return None
    return perm


def apply_state(config, state):
    """Apply order, swaps, names, and colours. Return ``config``.

    ``config`` holds ``iids``, ``groups``, ``aligned``, ``perm``,
    ``hexes``, ``order``, ``align_method``, and ``language``. Column
    swaps change ``aligned`` and ``perm``. Colours replace ``hexes``.
    ``names`` is the display name of each column. ``sample_order`` is
    the order written to ``order.tsv``.
    """
    language = config.get("language", "en")
    iids = [str(item) for item in config["iids"]]
    groups = [str(item) for item in config["groups"]]
    aligned = config["aligned"]
    perm = config["perm"]
    hexes = config["hexes"]
    ks = sorted(int(k) for k in aligned)
    if "k" not in state:
        _exit("state_missing", language, field="k")
    state_k = _as_int_list(state["k"])
    if state_k != ks:
        _exit("state_k", language, state_k=_join(state_k), cli_k=_join(ks))
    if "align_method" not in state:
        _exit("state_missing", language, field="align_method")
    method = state["align_method"]
    if method != config["align_method"]:
        _exit(
            "state_method",
            language,
            state_method=method,
            cli_method=config["align_method"],
        )
    sample_order = state.get("sample_order")
    if not isinstance(sample_order, list):
        _exit("state_missing", language, field="sample_order")
    pos = {iid: index for index, iid in enumerate(iids)}
    seen = set()
    order = []
    appearance = []
    seen_groups = set()
    for raw in sample_order:
        iid = str(raw)
        if iid not in pos:
            _exit("state_unknown_iid", language, iid=iid)
        if iid in seen:
            _exit("state_duplicate_iid", language, iid=iid)
        seen.add(iid)
        index = pos[iid]
        order.append(index)
        group = groups[index]
        if group not in seen_groups:
            seen_groups.add(group)
            appearance.append(group)
    for iid in iids:
        if iid not in seen:
            _exit("state_missing_iid", language, iid=iid)
    if "group_order" in state and state["group_order"] is not None:
        wanted = [str(item) for item in state["group_order"]]
        known = set(groups)
        for name in wanted:
            if name not in known:
                _exit("state_group_unknown", language, name=name)
        for name in appearance:
            if name not in set(wanted):
                _exit("state_group_missing", language, name=name)
        if wanted != appearance:
            _exit(
                "state_group_order",
                language,
                state_groups=_join(wanted),
                sample_groups=_join(appearance),
            )
    labels = state.get("sample_groups")
    if labels is not None:
        if not isinstance(labels, list) or len(labels) != len(sample_order):
            _exit(
                "state_sample_groups",
                language,
                got=0 if not isinstance(labels, list) else len(labels),
                n=len(sample_order),
            )
        for raw, label in zip(sample_order, labels):
            iid = str(raw)
            if str(label) != groups[pos[iid]]:
                _exit(
                    "state_sample_group",
                    language,
                    iid=iid,
                    state_group=label,
                    file_group=groups[pos[iid]],
                )
    swaps = state.get("swaps") or {}
    if not isinstance(swaps, dict):
        _exit("state_missing", language, field="swaps")
    flag = bool(state.get("alignment_overridden", False))
    clusters = state.get("clusters") or {}
    if not isinstance(clusters, dict):
        _exit("state_missing", language, field="clusters")
    names = {}
    applied = {}
    any_swap = False
    for k in ks:
        raw_perm = None
        if str(k) in swaps:
            raw_perm = swaps[str(k)]
        elif k in swaps:
            raw_perm = swaps[k]
        if raw_perm is None:
            column_perm = list(range(k))
        else:
            column_perm = _permutation(raw_perm, k)
            if column_perm is None:
                _exit("state_swap", language, k=k, n=k)
        applied[k] = column_perm
        moved = column_perm != list(range(k))
        if moved:
            any_swap = True
            if not flag:
                _exit("state_flag", language, k=k)
            aligned[k] = np.array(aligned[k][:, column_perm], copy=True)
            perm[k] = [int(perm[k][index]) for index in column_perm]
            hexes[k] = [hexes[k][index] for index in column_perm]
        items = None
        if str(k) in clusters:
            items = clusters[str(k)]
        elif k in clusters:
            items = clusters[k]
        if items is None:
            names[k] = ["C%d" % (col + 1) for col in range(k)]
            continue
        if not isinstance(items, list) or len(items) != k:
            _exit(
                "state_clusters",
                language,
                k=k,
                got=0 if not isinstance(items, list) else len(items),
                n=k,
            )
        colours = []
        labels_k = []
        for item in items:
            if not isinstance(item, dict) or "name" not in item or "colour" not in item:
                _exit("state_missing", language, field="clusters")
            labels_k.append(str(item["name"]))
            colours.append(norm_hex(str(item["colour"]), language=language))
        if len(set(colours)) != k:
            _exit("state_duplicate_colour", language, k=k)
        hexes[k] = colours
        names[k] = labels_k
    config["order"] = order
    config["spans"] = spans_of(order, groups)
    config["names"] = names
    config["swaps"] = applied
    config["alignment_overridden"] = bool(flag or any_swap)
    config["aligned"] = aligned
    config["perm"] = perm
    config["hexes"] = hexes
    return config


def state_from_run(result):
    """Build a ``qbar-state`` dict from a mapping of one finished run.

    ``RunResult`` does not carry sample ids or input hashes. ``result``
    is a dict with ``iids``, ``groups``, ``order``, ``colours``, ``k``,
    ``align_method``, and ``inputs``. Optional keys are ``names``,
    ``swaps``, ``alignment_overridden``, ``plot``, ``qbar_version``, and
    ``git_commit``.
    """
    if not isinstance(result, dict):
        raise TypeError("state_from_run expects a dict")
    iids = [str(item) for item in result["iids"]]
    groups = [str(item) for item in result["groups"]]
    order = [int(item) for item in result["order"]]
    sample_order = [iids[index] for index in order]
    sample_groups = [groups[index] for index in order]
    group_order = []
    seen = set()
    for name in sample_groups:
        if name in seen:
            continue
        seen.add(name)
        group_order.append(name)
    ks = [int(k) for k in result["k"]]
    colours = result["colours"]
    names = result.get("names") or {}
    swaps = result.get("swaps") or {}
    overridden = bool(result.get("alignment_overridden", False))
    clusters = {}
    swap_out = {}
    for k in ks:
        hexes = colours[k] if k in colours else colours[str(k)]
        if k in names:
            labels = names[k]
        elif str(k) in names:
            labels = names[str(k)]
        else:
            labels = ["C%d" % (col + 1) for col in range(k)]
        clusters[str(k)] = [
            {"name": str(labels[col]), "colour": str(hexes[col])}
            for col in range(k)
        ]
        if k in swaps:
            column_perm = [int(item) for item in swaps[k]]
        elif str(k) in swaps:
            column_perm = [int(item) for item in swaps[str(k)]]
        else:
            column_perm = list(range(k))
        swap_out[str(k)] = column_perm
        if column_perm != list(range(k)):
            overridden = True
    inputs = []
    for item in result["inputs"]:
        inputs.append({
            "role": str(item["role"]),
            "name": str(item["name"]),
            "sha256": str(item["sha256"]),
        })
    return {
        "schema": SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "qbar_version": str(result.get("qbar_version") or ""),
        "git_commit": str(result.get("git_commit") or "unknown"),
        "inputs": inputs,
        "k": ks,
        "align_method": str(result["align_method"]),
        "plot": result.get("plot") or {},
        "group_order": group_order,
        "sample_order": sample_order,
        "sample_groups": sample_groups,
        "clusters": clusters,
        "swaps": swap_out,
        "alignment_overridden": overridden,
    }


def order_txt(state):
    """One iid per line, the text ``--order-file`` already accepts."""
    return "".join("%s\n" % iid for iid in state["sample_order"])


def colours_tsv(state):
    """Name, tab, ``#rrggbb``. See the module docstring for ``parse_colors``."""
    lines = []
    for k in state["k"]:
        items = state["clusters"][str(k)]
        for item in items:
            lines.append("%s\t%s" % (item["name"], item["colour"]))
    return "\n".join(lines) + ("\n" if lines else "")


def write_state_json(path, state):
    """Write ``state`` as UTF-8 JSON, indent 2, ASCII escapes, trailing newline."""
    text = json.dumps(state, indent=2, ensure_ascii=True, sort_keys=False, allow_nan=False)
    if not text.endswith("\n"):
        text += "\n"
    folder = os.path.dirname(os.path.abspath(path))
    if folder:
        os.makedirs(folder, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
