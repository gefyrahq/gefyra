import unittest

from tests.base import GefyraBaseTest


class GefyraK3DTest(GefyraBaseTest, unittest.TestCase):
    provider = "k3d"
