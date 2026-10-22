#!/usr/bin/env python3
"""Checkout launcher for qbar.

When the repository root is on sys.path, ``import qbar`` loads this file
instead of the package under src/qbar. A repo-root module named qbar.py
would otherwise hide that package. This file points ``__path__`` at
src/qbar and executes that package's ``__init__.py`` here, so checkout
imports and ``python qbar.py`` use the same modules. ``__file__`` stays
this path, which checkout tests compare against the repository root.
"""
import ast
import importlib.util
import os
import sys

_ROOT = os.path.dirname(os.path.abspath(__file__))
_SRC_PKG = os.path.join(_ROOT, "src", "qbar")

# Make this module the qbar package before the package init runs.
__path__ = [_SRC_PKG]
__package__ = "qbar"
if __name__ == "__main__" and "qbar" not in sys.modules:
    sys.modules["qbar"] = sys.modules["__main__"]

_init_path = os.path.join(_SRC_PKG, "__init__.py")
with open(_init_path, encoding="utf-8") as _handle:
    exec(compile(_handle.read(), _init_path, "exec"), globals())

if __name__ == "__main__":
    sys.exit(main())
