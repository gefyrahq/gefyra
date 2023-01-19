import unittest

from tests.base import GefyraBaseTest


class GefyraK3DTest(unittest.TestCase, GefyraBaseTest):
    provider = "k3d"
