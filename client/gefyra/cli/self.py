import click


@click.group(
    "self",
    help="Manage this Gefyra executable",
)
@click.pass_context
def _self(ctx: click.Context):
    pass


@_self.command(
    "restore",
    help="Restore the local Gefyra client installation",
)
def restore():
    pass


@_self.command(
    "update",
    help="Update the local Gefyra client installation",
)
def update():
    pass
