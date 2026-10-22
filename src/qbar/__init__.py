__version__ = "0.2.0.dev0"

# Re-export the implementation so `import qbar` after installation exposes
# the same names as a checkout (qbar.main, qbar.build_parser, and the rest).
from qbar import cli as _cli

__doc__ = _cli.__doc__
for _name, _value in vars(_cli).items():
    if _name.startswith("_"):
        continue
    globals()[_name] = _value
del _name, _value, _cli
