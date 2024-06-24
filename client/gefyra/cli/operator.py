import click
from gefyra.cli.utils import AliasedGroup, standard_error_handler


@click.group("operator", cls=AliasedGroup, help="Manage operator installation")
@click.pass_context
def operator(ctx):
    pass


@operator.command(
    "update",
    help=("Update operator to latest or specific version."),
)
@click.option(
    "--version",
    help="Set specific version to update operator to.",
    required=False,
    type=str,
)
@standard_error_handler
def update(version):
    from gefyra import api

    api.operator.update(
        version=version,
    )
