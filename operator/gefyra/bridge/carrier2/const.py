_cmd_fmt = "RUST_LOG={level}; kill -SIGQUIT $(cat /tmp/carrier2.pid); if [ $? -eq 0 ]; then RUST_LOG={level} carrier2 -c /tmp/config.yaml -u -d &> /tmp/carrier.log; else RUST_LOG={level} carrier2 -c /tmp/config.yaml -d &> /tmp/carrier.log; fi"  # noqa
RELOAD_CARRIER2_DEBUG = _cmd_fmt.format(level="debug")
RELOAD_CARRIER2_INFO = _cmd_fmt.format(level="info")
