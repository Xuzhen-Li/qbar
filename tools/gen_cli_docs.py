#!/usr/bin/env python3
"""Write docs/cli.md from qbar.build_parser().

The page is built from the parser actions. It does not call format_help(),
because that heading differs across Python versions.
"""

import argparse
import os
import sys


def _repo_root():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _format_default(value):
    if value is None:
        return "not set"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, str) and value == "":
        return '""'
    if isinstance(value, (list, tuple)):
        if len(value) == 0:
            return "[]"
        return ", ".join(str(item) for item in value)
    return str(value)


def render_cli_markdown(parser=None):
    """Return the command reference as a string ending in a newline."""
    if parser is None:
        root = _repo_root()
        if root not in sys.path:
            sys.path.insert(0, root)
        import qbar
        parser = qbar.build_parser()
    lines = [
        "# qbar command line",
        "",
        "Generated from `build_parser()`. The option text below is the help string the program ships. It is copied, not rewritten.",
        "",
    ]
    if parser.description:
        lines.append(parser.description)
        lines.append("")
    if parser.epilog:
        lines.append("## Notes")
        lines.append("")
        lines.append(parser.epilog)
        lines.append("")
    lines.append("## Options")
    lines.append("")
    for action in parser._actions:
        if not action.option_strings:
            continue
        lines.append("### `%s`" % ", ".join(action.option_strings))
        lines.append("")
        if action.help:
            lines.append(action.help)
            lines.append("")
        facts = []
        if action.choices is not None:
            facts.append("Choices: %s" % ", ".join(str(item) for item in action.choices))
        if action.required:
            facts.append("Required: yes")
        if action.nargs not in (None, 0, argparse.SUPPRESS):
            facts.append("Arguments: %s" % action.nargs)
        if action.default is not argparse.SUPPRESS and not isinstance(action, argparse._HelpAction):
            facts.append("Default: %s" % _format_default(action.default))
        if action.metavar:
            facts.append("Metavar: %s" % action.metavar)
        for fact in facts:
            lines.append("- %s" % fact)
        if facts:
            lines.append("")
    lines.extend(_config_lines())
    text = "\n".join(lines)
    if not text.endswith("\n"):
        text += "\n"
    return text


def _config_lines():
    """Extra command reference for --config. Not part of format_help()."""
    text = """## Config file

`--config PATH` reads a YAML mapping. It is omitted by default. PyYAML is imported only when this flag is present. If PyYAML is missing, qbar exits and the message names `pip install "qbar[config]"`.

Precedence is the command line, then the config file, then the defaults from `build_parser`. A flag that is present on the command line wins, including when the value equals the default. A flag that is absent does not replace a value from the file.

Keys are argparse dest names, such as `align_method` and `order_mode`. `align-method` and `--align-method` are accepted and mapped to `align_method`. The key `config` is rejected. The key `state` is allowed and means the same thing as `--state`. `--q` and `--outdir` may be omitted on the command line when the file sets them. A sample id file (`ids`, `fam`, or `ind`) can be set in the file as well. The run still requires one id source.

`on`, `off`, `yes`, and `no` must be quoted when the option expects a string. PyYAML 1.1 reads those words as booleans. A repeated YAML key keeps the last value.

Paths in the file are resolved against the current working directory, the same way as paths on the command line. The directory that contains the config file is not used.

A `store_true` key set to true in the file stays true. The command line cannot turn it off. Those flags have no `--no-` form. The exception is `align`, which has `--align` and `--no-align`. Edit the file to turn the key off.

A float that is not finite is an error and the message names the key. That includes `.nan`, `.inf`, `-.inf`, and the string `NaN` on a float key. The same check applies to a command-line float when `--config` is used, so `config_resolved.json` is not written.

When `--config` is passed and the run finishes, the output directory contains `config_resolved.json`. Keys are sorted, indent is 2, and the file ends with a newline. Each dest is the value the run used. `sources` maps each dest to `cli`, `config`, or `default`. `config_file` is the base name of the YAML file. `config_sha256` is the SHA256 of its bytes. The directory is not stored. File-valued options are base names only.

`--state` is applied after that resolution. It replaces sample order and colours. `state_override` records `order` and `colours` when both `--config` and `--state` are used. If the file sets `align_method`, the command line does not pass `--align-method`, and the state names a different method, the run uses the state method. `state_override.align_method` records the config value and the state value. A command-line `--align-method` must still match the state.

`color`, `color_file`, and `order_file` from the file are ignored when `--state` is set. stderr prints one line naming those keys. `state_override` records each one as the config value and `used: state`. File values in that record are base names. Passing `--color`, `--color-file`, or `--order-file` on the command line together with `--state` is still an error.

```yaml
q:
  - k2.Q
  - k3.Q
ids: ids.txt
align_method: hungarian
outdir: out
```
"""
    return text.splitlines()


def main():
    dest = os.path.join(_repo_root(), "docs", "cli.md")
    text = render_cli_markdown()
    with open(dest, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
