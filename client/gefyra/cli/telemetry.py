import logging
import configparser
import uuid
from pathlib import Path

import click

from gefyra.configuration import __VERSION__
from gefyra.cli.utils import AliasedGroup, standard_error_handler


logger = logging.getLogger("gefyra")

########################################################################################
# Telemetry information
# We are collecting anonymous data about the usage of Gefyra as CLI
# All the data we collect is published here: ``
# This data is supposed to help us develop Gefyra and make it a better tool, prioritize
# issues and work on bugs, features and review of pull requests.
# If you do not which to send telemetry data this is totally fine.
# Just opt out via `gefyra telemetry off`.
########################################################################################

SENTRY_DSN = (
    "https://97c8c0409cb74a079a93f05021b329f0@o146863.ingest.sentry.io/4505119985172480"
)


class CliTelemetry:
    dir_name = ".gefyra"
    file_name = "config.ini"

    def __init__(self):
        # We're loading / creating a settings file in the home directory.
        home = Path.home()
        gefyra_dir = home / self.dir_name
        if gefyra_dir.exists():
            gefyra_settings_path = gefyra_dir / self.file_name
            if gefyra_settings_path.exists():
                config = self.load_config(str(gefyra_settings_path))
            else:
                config = self.create_config(gefyra_settings_path)
        else:
            config = self.create_config(gefyra_dir / self.file_name)
        try:
            config["telemetry"].getboolean("track")
            # This was added later and is here for backwards compatbility
            user_id = self._get_user_id(config)
        except KeyError:
            config = self.create_config(gefyra_dir / self.file_name)

        if config["telemetry"].getboolean("track"):
            self._init_tracker(user_id=user_id)

    def _init_tracker(self, user_id):
        from cli_tracker.sdk import CliTracker

        self.tracker = CliTracker(
            application="gefyra",
            dsn=SENTRY_DSN,
            release=__VERSION__,
            fingerprint=user_id,
        )

    def _get_user_id(self, config):
        if config["telemetry"].get("id"):
            user_id = config["telemetry"].get("id")
        else:
            user_id = self.create_id()
        return user_id

    def load_config(self, path):
        config = configparser.ConfigParser()
        config.read(path)
        self.path = path
        return config

    def create_config(self, path):
        config = configparser.ConfigParser()
        config["telemetry"] = {"track": "True", "id": str(uuid.uuid4())}
        output_file = Path(path)
        output_file.parent.mkdir(exist_ok=True, parents=True)

        with open(str(output_file), "w") as config_file:
            config.write(config_file)
        self.path = path
        return config

    def create_id(self):
        config = configparser.ConfigParser()
        config.read(self.path)
        user_id = str(uuid.uuid4())
        config["telemetry"]["id"] = user_id
        with open(str(self.path), "w") as config_file:
            config.write(config_file)
        return user_id

    def off(self):
        config = configparser.ConfigParser()
        config.read(self.path)
        config["telemetry"]["track"] = "False"
        with open(str(self.path), "w") as config_file:
            config.write(config_file)
        if hasattr(self, "tracker"):
            self.tracker.report_opt_out()
        logger.info("Disabled telemetry.")

    def on(self, test=False):
        config = configparser.ConfigParser()
        config.read(self.path)
        config["telemetry"]["track"] = "True"
        with open(str(self.path), "w") as config_file:
            config.write(config_file)
        user_id = self._get_user_id(config)
        self._init_tracker(user_id=user_id)
        if not test:
            self.tracker.report_opt_in()
        logger.info("Enabled telemetry.")


@click.group(
    name="telemetry", cls=AliasedGroup, help="Manage Gefyra's CLI telemetry settings"
)
@click.pass_context
def telemetry(ctx):
    pass


@telemetry.command("on", help="Turn on Gefyra's CLI telemetry")
@standard_error_handler
@click.pass_context
def on(ctx: click.Context):
    ctx.obj["telemetry"].on()


@telemetry.command("off", help="Turn off Gefyra's CLI telemetry")
@standard_error_handler
@click.pass_context
def off(ctx: click.Context):
    ctx.obj["telemetry"].off()


@telemetry.command("show", help="Shows Gefyra's current telemetry settings")
@standard_error_handler
@click.pass_context
def show(ctx: click.Context):
    if ctx.obj["telemetry"] and getattr(ctx.obj["telemetry"], "tracker", None):
        click.echo("Telemetry is enabled.")
    else:
        click.echo("Telemetry is disabled.")
