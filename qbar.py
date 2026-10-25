#!/usr/bin/env python3
"""Checkout launcher for qbar.

When the repository root is on sys.path, `import qbar` loads this file
instead of the src/qbar package. Loading src/qbar/cli.py with
`import qbar.cli` would fail for that reason. This module loads cli.py
under a private module name and re-exports its namespace. __file__ stays
this path so a checkout import still points at the repository root.
"""

import ast
import importlib.util
import os
import sys

_ROOT = os.path.dirname(os.path.abspath(__file__))
_CLI_PATH = os.path.join(_ROOT, "src", "qbar", "cli.py")
_INIT_PATH = os.path.join(_ROOT, "src", "qbar", "__init__.py")
_SKIP = {
    "__name__",
    "__loader__",
    "__package__",
    "__spec__",
    "__file__",
    "__cached__",
    "__builtins__",
}


def _load_cli():
    spec = importlib.util.spec_from_file_location("_qbar_cli", _CLI_PATH)
    if spec is None or spec.loader is None:
        raise ImportError("cannot load %s" % _CLI_PATH)
    module = importlib.util.module_from_spec(spec)
    # Register before exec so functions can see their own module.
    sys.modules["_qbar_cli"] = module
    spec.loader.exec_module(module)
    return module


def _read_version(path):
    with open(path, encoding="utf-8") as handle:
        tree = ast.parse(handle.read(), filename=path)
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == "__version__":
                value = node.value
                if isinstance(value, ast.Constant) and isinstance(value.value, str):
                    return value.value
    raise RuntimeError("__version__ is missing from %s" % path)


_cli = _load_cli()
for _name, _value in vars(_cli).items():
    if _name in _SKIP:
        continue
    globals()[_name] = _value
__version__ = _read_version(_INIT_PATH)
del _name, _value, _cli

if __name__ == "__main__":
    sys.exit(main())
