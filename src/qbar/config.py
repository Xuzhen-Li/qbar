"""Optional YAML settings.

``load_config`` reads one mapping with ``yaml.safe_load``. PyYAML is
imported only inside that function. A missing import exits with a message
that names ``pip install "qbar[config]"``.

Keys are argparse dest names. ``align-method`` and ``--align-method``
become ``align_method``. The key ``config`` is rejected. The key ``state``
is allowed and is the same dest as ``--state``.

``main`` applies precedence after it knows which dests were present on the
command line: command line, then this file, then parser defaults. A dest
that was present keeps the command-line value, including when that value
equals the default. Presence comes from a parse whose defaults are
``argparse.SUPPRESS``, not from a comparison with the default value.

``config_resolved.json`` is written only after a successful run that was
given ``--config``. Keys are sorted. Indent is 2. The file ends with a
newline. Each dest holds the value the run used. ``sources`` maps each
dest to ``cli``, ``config``, or ``default``. ``config_file`` is the base
name of the YAML file and ``config_sha256`` is the SHA256 of its bytes.
The directory is not stored. File-valued options are base names only.

``--state`` is applied after that resolution and replaces sample order and
colours. ``state_override`` records that when both were used. If the file
sets ``align_method``, the command line does not pass ``--align-method``,
and the state names a different method, the run uses the state method.
``state_override.align_method`` records the config value and the state
value. ``sources`` for that dest stays ``config``. A command-line
``--align-method`` must still match the state.

``color``, ``color_file``, and ``order_file`` that come from this file are
ignored when ``--state`` is set. ``main`` clears them before ``run`` and
records each under ``state_override`` as the config value and
``used: state``. The same flags on the command line still error.

A float that is not finite is an error that names the dest. The same
check runs on command-line floats before ``config_resolved.json`` is
encoded, so ``json.dumps`` is not given ``NaN`` or an infinity.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os

from .messages import text as _msg

# Dest names whose resolved JSON values are base names, never directories.
FILE_DESTS = frozenset({
    "q",
    "fam",
    "ids",
    "ind",
    "groups",
    "order_file",
    "color_file",
    "logs",
    "logs_map",
    "low_confidence_table",
    "pca",
    "state",
    "outdir",
    "config",
})


def _exit(msg_key, language, **values):
    raise SystemExit(_msg(msg_key, language, **values))


def _type_name(value):
    if value is None:
        return "null"
    if type(value) is bool:
        return "bool"
    if type(value) is int:
        return "int"
    if type(value) is float:
        return "float"
    if type(value) is str:
        return "str"
    if type(value) is list:
        return "list"
    if isinstance(value, dict):
        return "mapping"
    return type(value).__name__


def _fail_type(dest, expected, value, language, shown=None):
    got = _type_name(value) if shown is None else shown
    _exit("config_type", language, option=dest, expected=expected, got=got)


def _dest_name(key):
    text = key[2:] if key.startswith("--") else key
    return text.replace("-", "_")


def _actions_by_dest(parser):
    found = {}
    for action in parser._actions:
        if action.dest == "help":
            continue
        found.setdefault(action.dest, []).append(action)
    return found


def _bool_mode(actions):
    true = any(isinstance(action, argparse._StoreTrueAction) for action in actions)
    false = any(isinstance(action, argparse._StoreFalseAction) for action in actions)
    if true and false:
        return "tri"
    if true or false:
        return "bool"
    return None


def _is_list_action(action):
    if isinstance(action, argparse._AppendAction):
        return True
    return action.nargs == "+"


def _check_choices(action, dest, value, language):
    if action.choices is None or value in action.choices:
        return
    if type(value) is str and len(value) <= 80:
        shown = value
    else:
        shown = _type_name(value)
    expected = "one of " + ", ".join(str(item) for item in action.choices)
    _fail_type(dest, expected, value, language, shown=shown)


def _coerce_text_or_typed(action, dest, value, language):
    """Coerce one scalar the way the flag's type and choices would."""
    if action.type is None:
        if type(value) is not str:
            _fail_type(dest, "str", value, language)
        _check_choices(action, dest, value, language)
        return value
    if type(value) is bool:
        expected = "int" if action.type is int else "float" if action.type is float else "str"
        _fail_type(dest, expected, value, language)
    if action.type is int and type(value) is int:
        result = value
    elif action.type is float and type(value) in (int, float):
        result = float(value)
    elif type(value) is str:
        try:
            result = action.type(value)
        except (TypeError, ValueError, argparse.ArgumentTypeError):
            expected = "int" if action.type is int else "float" if action.type is float else "str"
            _fail_type(dest, expected, value, language)
        if action.type is int and type(result) is not int:
            _fail_type(dest, "int", value, language)
        if action.type is float:
            result = float(result)
    else:
        expected = "int" if action.type is int else "float" if action.type is float else "str"
        _fail_type(dest, expected, value, language)
    _check_choices(action, dest, result, language)
    return result


def _coerce_list(action, dest, value, language):
    if value is None:
        if action.default is None and not action.required:
            return None
        _fail_type(dest, "list", value, language)
    if type(value) is not list:
        _fail_type(dest, "list", value, language)
    if action.nargs == "+" and len(value) == 0:
        _fail_type(dest, "non-empty list", value, language)
    out = []
    for item in value:
        if item is None:
            _fail_type(dest, "str", item, language)
        out.append(_coerce_text_or_typed(action, dest, item, language))
    return out


def _coerce_scalar(action, dest, value, language):
    if value is None:
        if action.default is None and not action.required:
            return None
        expected = "int" if action.type is int else "float" if action.type is float else "str"
        _fail_type(dest, expected, value, language)
    return _coerce_text_or_typed(action, dest, value, language)


def _reject_nonfinite(dest, value, language):
    """Exit when a float dest is NaN or an infinity. The message names dest."""
    if type(value) is float and not math.isfinite(value):
        _exit("config_nonfinite", language, option=dest)
    if type(value) is list or type(value) is tuple:
        for item in value:
            _reject_nonfinite(dest, item, language)
    elif type(value) is dict:
        for item in value.values():
            _reject_nonfinite(dest, item, language)


def _coerce(actions, dest, value, language):
    mode = _bool_mode(actions)
    if mode == "tri":
        if value is None or type(value) is bool:
            result = value
        else:
            _fail_type(dest, "bool or null", value, language)
    elif mode == "bool":
        if type(value) is bool:
            result = value
        else:
            _fail_type(dest, "bool", value, language)
    else:
        action = actions[0]
        if _is_list_action(action):
            result = _coerce_list(action, dest, value, language)
        else:
            result = _coerce_scalar(action, dest, value, language)
    _reject_nonfinite(dest, result, language)
    return result


def load_config(path, *, language="en"):
    """Return the YAML mapping at ``path``.

    Keys are returned as written. ``main`` checks them against dest names.
    PyYAML is imported here. If it is missing, this exits and the message
    names ``pip install "qbar[config]"``. The top level must be a mapping.
    """
    # Decode before importing PyYAML so a bad byte fails without that package.
    try:
        with open(path, encoding="utf-8") as handle:
            raw = handle.read()
    except OSError:
        _exit("config_open", language, path=path)
    except UnicodeError:
        _exit("config_yaml", language, name=os.path.basename(path))
    try:
        import yaml
    except ImportError:
        _exit("config_needs_yaml", language)
    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError:
        _exit("config_yaml", language, name=os.path.basename(path))
    if not isinstance(data, dict):
        _exit("config_mapping", language, got=_type_name(data))
    return data


def validate_config(data, parser, *, language="en"):
    """Return dest to coerced value. Reject unknown keys and bad types."""
    known = _actions_by_dest(parser)
    coerced = {}
    seen = set()
    for key, raw in data.items():
        if type(key) is not str:
            _exit("config_key_type", language, got=_type_name(key))
        dest = _dest_name(key)
        if dest == "config":
            _exit("config_rejected", language)
        if dest in seen:
            _exit("config_duplicate", language, option=dest)
        seen.add(dest)
        if dest not in known:
            _exit("config_unknown", language, option=key)
        coerced[dest] = _coerce(known[dest], dest, raw, language)
    return coerced


def apply_file_defaults(parser, data, explicit, *, language="en"):
    """Set defaults from ``data`` for dests the command line did not pass.

    ``explicit`` is the set of dests present on the command line. Those
    dests keep the parser defaults so the command line replaces the file.
    Required dests that the file supplies are no longer required.
    Returns the coerced mapping, including dests the command line also set.
    """
    coerced = validate_config(data, parser, language=language)
    defaults = {}
    for dest, value in coerced.items():
        if dest in explicit:
            continue
        defaults[dest] = value
    if defaults:
        for action in parser._actions:
            if action.dest in defaults and action.required:
                action.required = False
        parser.set_defaults(**defaults)
    return coerced


def option_dests(parser):
    """Dest names in parser order, without ``help``."""
    dests = []
    for action in parser._actions:
        if action.dest == "help":
            continue
        if action.dest not in dests:
            dests.append(action.dest)
    return dests


def _base_name(value):
    if value is None:
        return None
    if isinstance(value, list):
        return [_base_name(item) for item in value]
    if isinstance(value, str):
        if value == "":
            return ""
        return os.path.basename(value)
    return value


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


def resolved_text(args, parser, config_path, explicit, coerced, state_override, language="en"):
    """JSON text of the resolved settings. File values are base names."""
    payload = {}
    sources = {}
    for dest in option_dests(parser):
        value = getattr(args, dest)
        _reject_nonfinite(dest, value, language)
        if dest in FILE_DESTS:
            value = _base_name(value)
        payload[dest] = value
        if dest in explicit:
            sources[dest] = "cli"
        elif dest in coerced:
            sources[dest] = "config"
        else:
            sources[dest] = "default"
    payload["sources"] = sources
    payload["config_file"] = os.path.basename(config_path)
    payload["config_sha256"] = file_sha256(config_path)
    if state_override:
        payload["state_override"] = state_override
    text = json.dumps(
        payload,
        indent=2,
        sort_keys=True,
        ensure_ascii=True,
        allow_nan=False,
    )
    if not text.endswith("\n"):
        text += "\n"
    return text


def write_resolved_text(outdir, text):
    """Write ``config_resolved.json`` in ``outdir``."""
    path = os.path.join(outdir, "config_resolved.json")
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
