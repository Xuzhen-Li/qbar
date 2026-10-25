__version__ = "0.2.0.dev0"

# Re-export the implementation so `import qbar` exposes the same names as
# before, except the drawing helpers, which load on first use.
from . import cli as _cli

__doc__ = _cli.__doc__
for _name, _value in vars(_cli).items():
    if _name.startswith("_"):
        continue
    globals()[_name] = _value
_kept = _cli
del _name, _value, _cli
cli = _kept
del _kept

from .api import write_run_json

_PLOT_EXPORTS = (
    "FONT_CANDIDATES",
    "Image",
    "ImageDraw",
    "ImageFont",
    "PALETTE",
    "ancestry_image",
    "assign_colors",
    "draw_rotated",
    "hex_rgb",
    "hsv_hex",
    "load_font",
    "next_free",
    "render",
    "text_wh",
)


def __getattr__(name):
    if name not in _PLOT_EXPORTS:
        raise AttributeError("module %r has no attribute %r" % (__name__, name))
    import importlib
    plot_static = importlib.import_module("qbar.plot_static")
    value = getattr(plot_static, name)
    globals()[name] = value
    return value


def __dir__():
    return sorted(set(globals()) | set(_PLOT_EXPORTS))
