#!/usr/bin/env python3
"""
Generate markdown documentation for the Gefyra CLI.

This script introspects the Click CLI and generates markdown documentation
matching the Docus format used in gefyra-docs.

Usage:
    gefyra-docs --output ../gefyra-docs/content/en/1.quick-start/5.cli.md
"""

from pathlib import Path
from typing import Optional

import click

# Static examples for commands - easier to maintain than docstrings
EXAMPLES = {
    "bridge": """
```sh
gefyra bridge create
gefyra bridge list
gefyra bridge delete my-bridge
```
""",
    "bridge create": """
```sh
gefyra bridge create -t mycontainer -p 8080:8080 --mount my-mount
```
""",
    "bridge delete": """
```sh
gefyra bridge delete my-bridge
gefyra bridge rm my-bridge
```
""",
    "bridge list": """
```sh
gefyra bridge list
gefyra bridge ls
```
""",
    "bridge inspect": """
```sh
gefyra bridge inspect my-bridge
```
""",
    "clients": """
```sh
gefyra clients create
gefyra clients list
gefyra clients delete my-client
```
""",
    "clients create": """
```sh
gefyra clients create -n 2 # creates 2 clients
```
""",
    "clients list": """
```sh
gefyra clients list
gefyra clients ls
```
""",
    "clients inspect": """
```sh
gefyra clients inspect <client-id>
gefyra clients inspect my-client-id
```
""",
    "clients config": """
```sh
gefyra clients config -h 1.1.1.1 my-client-id
```
""",
    "clients delete": """
```sh
gefyra clients delete my-client-id
gefyra clients rm my-client-id
gefyra clients remove my-client-id
```
""",
    "clients disconnect": """
```sh
gefyra clients disconnect my-client-id
```
""",
    "connections": """
```sh
gefyra connections connect -f con_file.json -n my-connection
gefyra connections list
gefyra connections disconnect my-connection
```
""",
    "connections connect": """
```sh
gefyra connections connect -f con_file.json -n my-connection
```
""",
    "connections disconnect": """
```sh
gefyra connections disconnect my-connection
```
""",
    "connections list": """
```sh
gefyra connections list
```
""",
    "connections remove": """
```sh
gefyra connections rm my-connection
```
""",
    "connections inspect": """
```sh
gefyra connections inspect my-connection
```
""",
    "down": """
```sh
gefyra down
```
""",
    "install": """
```sh
gefyra install
```
""",
    "list": """
```sh
gefyra list
```
""",
    "mount": """
```sh
gefyra mount create --target deploy/my-deploy/my-container
gefyra mount list
gefyra mount delete my-mount
```
""",
    "mount create": """
```sh
gefyra mount create --target deploy/my-deploy/my-container -n default
```
""",
    "mount delete": """
```sh
gefyra mount delete my-mount
gefyra mount rm my-mount
```
""",
    "mount list": """
```sh
gefyra mount list
gefyra mount ls
```
""",
    "mount inspect": """
```sh
gefyra mount inspect my-mount
```
""",
    "operator": """
```sh
gefyra operator update
```
""",
    "operator update": """
```sh
gefyra operator update
```
""",
    "rm": """
```sh
gefyra rm mycontainer
```
""",
    "run": """
```sh
gefyra run -i pyserver -N mypyserver -n default
```
""",
    "self": """
```sh
gefyra self update
gefyra self restore
```
""",
    "self restore": """
```sh
gefyra self restore
```
""",
    "self update": """
```sh
gefyra self update
```
""",
    "status": """
```sh
gefyra status
```
""",
    "uninstall": """
```sh
gefyra uninstall
```
""",
    "up": """
```sh
gefyra up
```
""",
    "version": """
```sh
gefyra version
```
""",
}

# YAML frontmatter for the generated documentation
FRONTMATTER = """---
title: Command line tool (CLI)
description: Gefyra's CLI allows you to run containers on your local machine and connect them to Kubernetes-based resources.
navigation:
  title: CLI
  icon: i-lucide-square-terminal
---
"""

INTRO = """# Command line tool (CLI)

## Syntax

Use the following syntax to run `gefyra` commands from your terminal:

```sh
gefyra [-h] [-d] [action] [arguments]
```

where `action` and `arguments` are:
- `action`: specifies the operation that you want to perform, for example `up` or `bridge`
- `arguments`:  specifies the required and optional arguments for a specific action, for example `-n` or `--namespace`

Global flags are:
- `-h, --help`: show help message and exit
- `-d, --debug`: add debug output for each action
"""


def escape_angle_brackets(text: str) -> str:
    """Wrap <placeholder> terms in backticks so they render as code in markdown."""
    import re

    # Match <...> patterns not already in backticks (allows letters, digits, _, |, :, etc.)
    return re.sub(r"(?<!`)(<[^<>]+>)(?!`)", r"`\1`", text)


def get_option_names(param: click.Option) -> str:
    """Format option names with short and long forms."""
    names = []
    for opt in param.opts:
        names.append(f"`{opt}`")
    for opt in param.secondary_opts:
        names.append(f"`{opt}`")
    return ", ".join(names)


def get_aliases(cmd: click.Command) -> list[str]:
    """Extract aliases from AliasedCommand."""
    if hasattr(cmd, "alias") and cmd.alias:
        return list(cmd.alias)
    return []


def format_param_description(param: click.Parameter) -> str:
    """Format parameter description with additional info."""
    # Arguments don't have help attribute, only Options do
    desc = getattr(param, "help", "") or ""

    # Escape angle brackets in description
    desc = escape_angle_brackets(desc)

    # Add default value info (skip sentinel values and empty tuples)
    default = param.default
    is_flag = getattr(param, "is_flag", False)

    # Skip sentinel values (check by string representation or type name)
    skip_default = (
        default is None
        or default == ()
        or is_flag
        or (hasattr(default, "__class__") and "Sentinel" in str(type(default)))
        or str(default) == "Sentinel.UNSET"
    )

    if not skip_default:
        if desc:
            desc += f" (default: `{default}`)"
        else:
            desc = f"Default: `{default}`"

    # Add required marker
    if param.required:
        if desc:
            desc += " **(required)**"
        else:
            desc = "**(required)**"

    return desc


def generate_options_table(cmd: click.Command) -> str:
    """Generate a markdown table for command options."""
    options = [p for p in cmd.params if isinstance(p, click.Option)]

    if not options:
        return ""

    lines = [
        "",
        "**Arguments:**  ",
        "",
        "| Argument | Description |",
        "|:---------|:------------|",
    ]

    for opt in options:
        names = get_option_names(opt)
        desc = format_param_description(opt)
        lines.append(f"| {names} | {desc} |")

    return "\n".join(lines)


def generate_arguments_table(cmd: click.Command) -> str:
    """Generate a markdown table for positional arguments."""
    args = [p for p in cmd.params if isinstance(p, click.Argument)]

    if not args:
        return ""

    lines = [
        "",
        "**Positional Arguments:**  ",
        "",
        "| Argument | Description |",
        "|:---------|:------------|",
    ]

    for arg in args:
        name = f"`{arg.name}`"
        # Don't call format_param_description for arguments - just show required status
        desc = "**(required)**" if arg.required else ""
        lines.append(f"| {name} | {desc} |")

    return "\n".join(lines)


def generate_command_doc(
    cmd: click.Command,
    name: str,
    prefix: str = "",
    level: int = 3,
    is_subcommand: bool = False,
) -> str:
    """Generate documentation for a single command."""
    full_name = f"{prefix} {name}".strip() if prefix else name

    lines = []

    # Use bold text for subcommands with manual anchor
    if is_subcommand and prefix:
        anchor_id = f"{prefix}-{name}".replace(" ", "-").lower()
        lines.append(f'<a id="{anchor_id}"></a>')
        lines.append(f"**▶ {prefix} {name}**")
    else:
        heading = "#" * level
        lines.append(f"{heading} {name}")

    # Add aliases
    aliases = get_aliases(cmd)
    if aliases:
        alias_str = ", ".join(f"`{a}`" for a in aliases)
        lines.append(f"\n*Aliases: {alias_str}*")

    # Add help text
    if cmd.help:
        help_text = escape_angle_brackets(cmd.help)
        lines.append(f"\n{help_text}")

    # Add example
    example_key = full_name
    if example_key in EXAMPLES:
        lines.append(f"\n**Example:**\n{EXAMPLES[example_key]}")

    # Add arguments table
    args_table = generate_arguments_table(cmd)
    if args_table:
        lines.append(args_table)

    # Add options table
    options_table = generate_options_table(cmd)
    if options_table:
        lines.append(options_table)

    return "\n".join(lines)


def generate_group_doc(
    group: click.Group,
    name: str,
    prefix: str = "",
    level: int = 3,
    is_toplevel: bool = True,
) -> str:
    """Generate documentation for a command group and its subcommands."""
    full_name = f"{prefix} {name}".strip() if prefix else name
    heading = "#" * level

    lines = [f"{heading} {name}"]

    # Add aliases
    aliases = get_aliases(group)
    if aliases:
        alias_str = ", ".join(f"`{a}`" for a in aliases)
        lines.append(f"\n*Aliases: {alias_str}*")

    # Add help text
    if group.help:
        help_text = escape_angle_brackets(group.help)
        lines.append(f"\n{help_text}")

    # Add example for the group itself
    if full_name in EXAMPLES:
        lines.append(f"\n**Example:**\n{EXAMPLES[full_name]}")

    # Add subcommands overview for top-level groups
    subcommands = sorted(group.commands.items(), key=lambda x: x[0])
    visible_subcommands = [(n, c) for n, c in subcommands if not c.hidden]

    if visible_subcommands and is_toplevel:
        lines.append("\n**Subcommands:**")
        for subcmd_name, subcmd in visible_subcommands:
            short_help = (
                escape_angle_brackets(subcmd.get_short_help_str(limit=60))
                if subcmd.help
                else ""
            )
            lines.append(
                f"- [`{name} {subcmd_name}`](#{name}-{subcmd_name}) — {short_help}"
            )

    # Generate docs for subcommands (sorted alphabetically)
    for i, (subcmd_name, subcmd) in enumerate(visible_subcommands):
        # Add separator between subcommands
        lines.append("")
        if isinstance(subcmd, click.Group):
            lines.append(
                generate_group_doc(
                    subcmd, subcmd_name, full_name, level + 1, is_toplevel=False
                )
            )
        else:
            lines.append(
                generate_command_doc(
                    subcmd, subcmd_name, full_name, level + 1, is_subcommand=True
                )
            )

    return "\n".join(lines)


def generate_toc(cli: click.Group) -> str:
    """Generate a table of contents for all commands."""
    lines = [
        "## Commands Overview",
        "",
        "| Command | Description |",
        "|:--------|:------------|",
    ]

    commands = sorted(cli.commands.items(), key=lambda x: x[0])
    for cmd_name, cmd in commands:
        if cmd.hidden:
            continue
        short_help = (
            escape_angle_brackets(cmd.get_short_help_str(limit=80)) if cmd.help else ""
        )
        lines.append(f"| [`{cmd_name}`](#{cmd_name}) | {short_help} |")

    lines.append("")
    return "\n".join(lines)


def generate_docs(output: Optional[str] = None) -> str:
    """
    Generate CLI documentation markdown.

    Args:
        output: Optional file path to write documentation to.

    Returns:
        The generated markdown string.
    """
    # Import CLI here to avoid circular imports and ensure all commands are registered
    from gefyra.cli.main import cli

    lines = [FRONTMATTER, INTRO]

    # Add table of contents
    lines.append(generate_toc(cli))

    # Get all top-level commands sorted alphabetically
    commands = sorted(cli.commands.items(), key=lambda x: x[0])

    for cmd_name, cmd in commands:
        if cmd.hidden:
            continue

        # Add horizontal rule before each top-level command
        lines.append("---")
        lines.append("")

        if isinstance(cmd, click.Group):
            lines.append(generate_group_doc(cmd, cmd_name))
        else:
            lines.append(generate_command_doc(cmd, cmd_name))

        lines.append("")

    content = "\n".join(lines)

    if output:
        output_path = Path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content)
        print(f"Documentation written to {output_path}")

    return content


@click.command()
@click.option(
    "-o",
    "--output",
    type=click.Path(),
    help="Output file path for generated documentation",
)
def main(output: Optional[str] = None):
    """Generate markdown documentation for the Gefyra CLI."""
    content = generate_docs(output)
    if not output:
        print(content)


if __name__ == "__main__":
    main()
