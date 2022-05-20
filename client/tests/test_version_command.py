import logging

from gefyra.__main__ import version_parser, version
from gefyra import configuration


def test_version_command(caplog):
    with caplog.at_level(logging.INFO):
        args = version_parser.parse_args()
        version(configuration, not args.no_check)
    assert "Gefyra client version" in caplog.text


def test_version_command_no_check(caplog):
    with caplog.at_level(logging.INFO):
        args = version_parser.parse_args(["-n"])
        version(configuration, not args.no_check)
    assert "Gefyra client version" in caplog.text
