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
    text = "\n".join(lines)
    if not text.endswith("\n"):
        text += "\n"
    return text


def main():
    dest = os.path.join(_repo_root(), "docs", "cli.md")
    text = render_cli_markdown()
    with open(dest, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
