from gefyra.__main__ import run_parser, bridge_parser


def test_ip_port_mapper():
    args = run_parser.parse_args(
        [
            "--expose=8080:localhost:8080",
            "--expose=9090:127.0.0.1:9090",
            "--expose=7070:7070",
            "-i=1",
            "-N=test",
        ]
    )
    assert "9090" in args.expose
    assert "8080" in args.expose
    assert args.expose["9090"] == ("9090", "127.0.0.1")
    assert args.expose["8080"] == ("8080", "localhost")
    assert args.expose["7070"] == "7070"


def test_port_mapper():
    args = bridge_parser.parse_args(
        ["--port=8080:8080", "--port=9090:9090", "-C=test", "-N=random"]
    )
    assert "9090" in args.port
    assert "8080" in args.port
    assert args.port["9090"] == "9090"
    assert args.port["8080"] == "8080"
