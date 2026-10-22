#!/usr/bin/env python3
"""Checkout launcher for qbar.

When the repository root is on sys.path, ``import qbar`` loads this file
instead of the package under src/qbar. This file installs a package spec
whose parent is ``qbar`` and whose search path is src/qbar, then executes
that package's ``__init__.py`` here. The same spec is used when this file
is run as a script, where ``__spec__`` would otherwise be None. ``__file__``
stays this path, which checkout tests compare against the repository root.
"""
import ast
import importlib.machinery
import importlib.util
import os
import sys

_ROOT = os.path.dirname(os.path.abspath(__file__))
_SRC_PKG = os.path.join(_ROOT, "src", "qbar")

# A module spec for qbar.py has parent "". Relative imports then warn on
# 3.12 because __package__ does not match that parent. A package spec named
# qbar has parent "qbar".
__spec__ = importlib.machinery.ModuleSpec(
    "qbar", None, origin=__file__, is_package=True)
__spec__.submodule_search_locations = [_SRC_PKG]
__path__ = __spec__.submodule_search_locations
__package__ = __spec__.parent
if __name__ == "__main__" and "qbar" not in sys.modules:
    sys.modules["qbar"] = sys.modules["__main__"]

_init_path = os.path.join(_SRC_PKG, "__init__.py")
with open(_init_path, encoding="utf-8") as _handle:
    exec(compile(_handle.read(), _init_path, "exec"), globals())

if __name__ == "__main__":
    sys.exit(main())
