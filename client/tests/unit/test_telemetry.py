import logging
import os
from pathlib import Path
import unittest

from gefyra.local.telemetry import CliTelemetry
import gefyra.__main__ as _gefyra


class MockCliTelemetry:
    @staticmethod
    def on(cls):
        return True

    @staticmethod
    def off(cls):
        pass


class TelemetryTest(unittest.TestCase):
    config_pre = "/.gefyra/config.ini"
    config_post = "/.gefyra/config.bak.ini"

    def setUp(self):
        home = str(Path.home())
        os.rename(self.config_path, home + self.config_post)
        return super().setUp()

    def tearDown(self) -> None:
        home = str(Path.home())
        os.rename(home + self.config_post, self.config_path)
        return super().tearDown()

    @property
    def config_path(self):
        return str(Path.home()) + self.config_pre

    def _init_tracker(self):
        self.tracker = CliTelemetry()
        # Make sure events are not sent
        self.tracker.tracker.sentry._client.transport = None

    def test_config_file_created(self):
        self.assertFalse(os.path.isfile(self.config_path))
        self._init_tracker()
        self.assertTrue(os.path.isfile(self.config_path))

    def test_config_file_read(self):
        self._init_tracker()
        config = self.tracker.load_config(self.config_path)
        self.assertTrue(config["telemetry"].getboolean("track"))

    def test_opt_out(self):
        self._init_tracker()
        self.tracker.off()
        config = self.tracker.load_config(self.config_path)
        self.assertFalse(config["telemetry"].getboolean("track"))

    def test_opt_in(self):
        self._init_tracker()
        self.tracker.on(test=True)
        config = self.tracker.load_config(self.config_path)
        self.assertTrue(config["telemetry"].getboolean("track"))


def test_telemetry_on(monkeypatch):
    monkeypatch.setattr(_gefyra, "CliTelemetry", MockCliTelemetry)
    _gefyra.telemetry_command(True, False)


def test_telemetry_off(monkeypatch):
    monkeypatch.setattr(_gefyra, "CliTelemetry", MockCliTelemetry)
    _gefyra.telemetry_command(False, True)


def test_telemetry_invalid(caplog):
    caplog.set_level(logging.INFO)
    _gefyra.telemetry_command(True, True)
    assert "Invalid flags" in caplog.text
    caplog.clear()
    assert "Invalid flags" not in caplog.text
    _gefyra.telemetry_command(False, False)
    assert "Invalid flags" in caplog.text
