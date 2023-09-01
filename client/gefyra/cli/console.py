import click


def heading(text: str):
    click.echo(click.style(text, bold=True))


def error(text: str):
    click.echo(click.style(text, fg="red"))


def info(text: str):
    click.echo(text)


def success(text: str):
    click.echo(click.style(text, fg="green"))
