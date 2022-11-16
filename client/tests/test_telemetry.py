import os
from pathlib import Path
import unittest

from gefyra.local.telemetry import CliTelemetry


class TelemetryTest(unittest.TestCase):
    config_pre = "/.gefyra/config.ini"
    config_post = "/.gefyra/config.bak.ini"

    def setUp(self):
        home = str(Path.home())
        os.rename(home + self.config_pre, home + self.config_post)
        self.tracker = CliTelemetry()
        # Make sure events are not sent
        self.tracker.tracker.sentry._client.transport = None
        return super().setUp()

    def tearDown(self) -> None:
        home = str(Path.home())
        os.rename(home + self.config_post, home + self.config_pre)
        return super().tearDown()

    def test_config_file_created(self):
        home = str(Path.home())
        self.assertTrue(os.path.isfile(home + self.config_pre))

    def test_config_file_read(self):
        pass

    def test_opt_in(self):
        pass

    def test_opt_out(self):
        pass
