import unittest

from tests.e2e.base import GefyraBaseTest


class GefyraK3DTest(GefyraBaseTest, unittest.TestCase):
    provider = "k3d"
