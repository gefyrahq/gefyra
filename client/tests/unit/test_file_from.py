import unittest
from gefyra.cli.utils import FileFromArgument, parse_file_from


class ParseFileFromTest(unittest.TestCase):
    def test_invalid_input_string(self):
        with self.assertRaises(ValueError):
            parse_file_from(None, None, ["invalid"])

    def test_invalid_input_format(self):
        with self.assertRaises(ValueError):
            parse_file_from(
                None,
                None,
                ["deployment/hello-world:/home/test.txt:/home/test.txt:/home/test.txt"],
            )

    def test_workload_source_destination(self):
        file_from_arguments = parse_file_from(
            None,
            None,
            ["deployment/hello-world/container:/home/test.txt:/home/test.txt"],
        )
        expected = (
            FileFromArgument(
                workload="deployment/hello-world/container",
                source="/home/test.txt",
                destination="/home/test.txt",
            ),
        )
        assert file_from_arguments == expected

    def test_workload_source(self):
        file_from_arguments = parse_file_from(
            None, None, ["deployment/hello-world/container:/home/test.txt"]
        )
        expected = (
            FileFromArgument(
                workload="deployment/hello-world/container",
                source="/home/test.txt",
                destination="/home/test.txt",
            ),
        )
        assert file_from_arguments == expected

    def test_duplicate_input(self):
        file_from_arguments = parse_file_from(
            None,
            None,
            [
                "deployment/hello-world/container:/home/test.txt",
                "deployment/hello-world/container:/home/test.txt",
            ],
        )
        expected = (
            FileFromArgument(
                workload="deployment/hello-world/container",
                source="/home/test.txt",
                destination="/home/test.txt",
            ),
        )
        assert file_from_arguments == expected

    def test_folder(self):
        file_from_arguments = parse_file_from(
            None,
            None,
            ["deployment/hello-world/container:/home:/home"],
        )
        expected = (
            FileFromArgument(
                workload="deployment/hello-world/container",
                source="/home",
                destination="/home",
            ),
        )
        assert file_from_arguments == expected
