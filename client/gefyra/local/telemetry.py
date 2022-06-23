import configparser
from pathlib import Path

from cli_tracker.sdk import CliTracker


class CliTelemetry:
    dir_name = ".gefyra"
    file_name = "config.ini"

    def __init__(self):
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
        except KeyError:
            config = self.create_config(gefyra_dir / self.file_name)

        if config["telemetry"].getboolean("track"):
            print("Tracking now")
            self._init_tracker()
        else:
            print("No Tracking")

    def _init_tracker(self):
        self.tracker = CliTracker(
            application="gefyra",
            dsn="https://a94b0a0194b045f79897f70f9727d299@sentry.unikube.io/3",
            release="0.8.1",
        )

    def load_config(self, path):
        config = configparser.ConfigParser()
        config.read(path)
        self.path = path
        return config

    def create_config(self, path):
        config = configparser.ConfigParser()
        config["telemetry"] = {"track": "True"}

        output_file = Path(path)
        output_file.parent.mkdir(exist_ok=True, parents=True)

        with open(str(output_file), "w") as config_file:
            config.write(config_file)
        self.path = path
        return config

    def off(self):
        config = configparser.ConfigParser()
        config.read(self.path)
        config["telemetry"]["track"] = "False"
        with open(str(self.path), "w") as config_file:
            config.write(config_file)
        if hasattr(self, "tracker"):
            self.tracker.report_opt_out()

    def on(self):
        config = configparser.ConfigParser()
        config.read(self.path)
        config["telemetry"]["track"] = "True"
        with open(str(self.path), "w") as config_file:
            config.write(config_file)
        self._init_tracker()
        self.tracker.report_opt_in()
