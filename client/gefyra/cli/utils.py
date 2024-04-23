from dataclasses import fields
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union
import click
from click import ClickException


def standard_error_handler(func):
    def wrapper(*args, **kwargs):
        try:
            result = func(*args, **kwargs)
            return result
        except Exception as e:  # noqa
            ce = ClickException(message=str(e))
            raise ce

    return wrapper


class AliasedCommand(click.Command):
    def __init__(
        self,
        name,
        alias: Optional[Iterable] = None,
        context_settings=None,
        callback=None,
        params=None,
        help=None,
        epilog=None,
        short_help=None,
        options_metavar="[OPTIONS]",
        add_help_option: bool = True,
        no_args_is_help: bool = False,
        hidden: bool = False,
        deprecated: bool = False,
    ) -> None:
        if not alias:
            alias = []
        super().__init__(
            name,
            context_settings,
            callback,
            params,
            help,
            epilog,
            short_help,
            options_metavar,
            add_help_option,
            no_args_is_help,
            hidden,
            deprecated,
        )
        self.alias = alias


class AliasedGroup(click.Group):
    command_class = AliasedCommand

    def get_command(self, ctx, cmd_name):
        rv = click.Group.get_command(self, ctx, cmd_name)
        if rv is not None:
            return rv
        for _, cmd in self.commands.items():
            if hasattr(cmd, "alias") and cmd_name in cmd.alias:
                return cmd
        matches = [x for x in self.list_commands(ctx) if x.startswith(cmd_name)]
        if not matches:
            return None
        elif len(matches) == 1:
            return click.Group.get_command(self, ctx, matches[0])
        ctx.fail(f"Too many matches: {', '.join(sorted(matches))}")

    def format_commands(self, ctx, formatter) -> None:
        commands = []
        _run_commands = sorted(self.commands.items())
        for subcommand, acmd in _run_commands:
            cmd = self.get_command(ctx, subcommand)
            # What is this, the tool lied about a command.  Ignore it
            if cmd is None:
                continue
            if cmd.hidden:
                continue

            if hasattr(acmd, "alias"):
                alias = ",".join(acmd.alias)
            else:
                alias = None
            commands.append((f"{subcommand} {'(' + alias + ')' if alias else ''}", cmd))

        # allow for 3 times the default spacing
        if len(commands):
            limit = formatter.width - 6 - max(len(cmd[0]) for cmd in commands)

            rows = []
            for subcommand, cmd in commands:
                help = cmd.get_short_help_str(limit)
                rows.append((subcommand, help))

            if rows:
                with formatter.section("Commands"):
                    formatter.write_dl(rows)

    def resolve_command(self, ctx, args):
        # always return the full command name
        _, cmd, args = super().resolve_command(ctx, args)
        return cmd.name, cmd, args


# https://stackoverflow.com/questions/50499340/specify-options-and-arguments-dynamically
class OptionEatAll(click.Option):
    def __init__(self, *args, **kwargs):
        self.save_other_options = kwargs.pop("save_other_options", True)
        nargs = kwargs.pop("nargs", -1)
        assert nargs == -1, "nargs, if set, must be -1 not {}".format(nargs)
        super(OptionEatAll, self).__init__(*args, **kwargs)
        self._previous_parser_process = None
        self._eat_all_parser = None

    def add_to_parser(self, parser, ctx):
        def parser_process(value, state):
            # method to hook to the parser.process
            done = False
            value = [value]
            if self.save_other_options:
                # grab everything up to the next option
                while state.rargs and not done:
                    for prefix in self._eat_all_parser.prefixes:
                        if state.rargs[0].startswith(prefix):
                            done = True
                    if not done:
                        value.append(state.rargs.pop(0))
            else:
                # grab everything remaining
                value += state.rargs
                state.rargs[:] = []
            value = tuple(value)

            # call the actual process
            self._previous_parser_process(value, state)

        retval = super(OptionEatAll, self).add_to_parser(parser, ctx)
        for name in self.opts:
            our_parser = parser._long_opt.get(name) or parser._short_opt.get(name)
            if our_parser:
                self._eat_all_parser = our_parser
                self._previous_parser_process = our_parser.process
                our_parser.process = parser_process
                break
        return retval


def multi_options(options):
    map_to_types = dict(
        array=str,
        number=float,
        string=str,
    )

    def decorator(f):
        for opt_params in reversed(options):
            param_decls = (
                "--" + opt_params["long"],
                opt_params["name"],
            )
            if "short" in opt_params and not opt_params["short"] is None:
                param_decls = ("-" + opt_params["short"], *param_decls)

            attrs = dict(
                required=opt_params["required"],
                type=map_to_types.get(opt_params["type"], opt_params["type"]),
                help=opt_params.get("help", ""),
            )
            if opt_params["type"] == "array":
                attrs["cls"] = OptionEatAll
                attrs["nargs"] = -1
                attrs["multiple"] = True

            click.option(*param_decls, **attrs)(f)
        return f

    return decorator


def installoptions_to_cli_options() -> List[Dict[str, Union[bool, str, Any, None]]]:
    from gefyra.types import GefyraInstallOptions

    result = []
    for _field in fields(GefyraInstallOptions):
        _data = dict(
            name=_field.name,
            long=_field.name.replace("_", "-"),
            short=_field.metadata.get("short"),
            required=False,
            help=_field.metadata.get("help"),
            type=_field.metadata.get("type") or "string",
        )
        result.append(_data)
    return result


def parse_ip_port_map(ctx, param, ports: Tuple[str]) -> dict:
    def v(p: str):
        if not p.isnumeric():
            raise RuntimeError(f"Invalid port {p}. Please use integer numbers as port.")
        return p

    # port - port
    res = {}
    for value in ports:
        _value = value.split(":")
        if len(_value) == 2:
            res[v(_value[1])] = v(_value[0])
        elif len(_value) == 3:
            res[v(_value[2])] = (_value[0], v(_value[1]))
        else:
            raise ValueError("Invalid value for port mapping.")
    return res


def parse_env(ctx, param, envs: Tuple[str]) -> List[str]:
    res = []
    for env in envs:
        if "=" not in env:
            raise ValueError("Invalid value for env variable. Please use 'ENV=value'.")
        res.append(env)
    return res


def parse_workload(ctx, param, workload: str) -> str:
    MSG = (
        "Invalid workload format. Please provide the workload "
        "in the format 'type/name' or 'type/name/container-name'."
    )
    if not workload:
        return workload
    if "/" not in workload:
        raise ValueError(MSG)
    return workload


def check_connection_name(ctx, param, selected: Optional[str] = None) -> str:
    from gefyra import api

    conn_list = api.list_connections()
    if not conn_list:
        raise click.UsageError(
            message="No Gefyra connection found. Please connect to a cluster first or run by "
            "providing a connection file or run 'gefyra up'."
        )
    conn_names = [conn.name for conn in conn_list]
    if selected and selected in conn_names:
        return selected
    elif selected:
        raise click.BadParameter(
            message=f"The connection name '{selected}' does not exist."
        )
    else:
        if "default" in conn_names and len(conn_names) == 1:
            connection_name = "default"
        else:
            raise click.MissingParameter(
                message="Please provide a connection name from: {conn_names}",
                param="connection-name",  # type: ignore
            )
        return connection_name
