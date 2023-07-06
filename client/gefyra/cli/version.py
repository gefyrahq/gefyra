import click
from gefyra.cli.console import info


@click.command()
@click.option(
    "-n",
    "--no-check",
    help="Do not check whether there is a new version",
    is_flag=True,
    default=False,
)
@click.pass_context
def version(ctx, no_check):
    import requests
    import gefyra.configuration as config

    info(f"Gefyra client version: {config.__VERSION__}")
    if not no_check:
        release = requests.get(
            "https://api.github.com/repos/gefyrahq/gefyra/releases/latest"
        )
        if release.status_code == 403:  # pragma: no cover
            info("Versions cannot be compared, as API rate limit was exceeded")
            return None
        latest_release_version = release.json()["tag_name"].replace("-", ".")
        if config.__VERSION__ != latest_release_version:  # pragma: no cover
            info(
                f"You are using gefyra version {config.__VERSION__}; however, version"
                f" {latest_release_version} is available."
            )
    return True
