import click

from gefyra.api import status
from gefyra.cli.utils import standard_error_handler


@click.command("status", help="Get Gefyra's status")
@standard_error_handler
def status_command():
    print(status())
