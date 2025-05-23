RELOAD_CARRIER2 = "RUST_LOG=debug; kill -SIGQUIT $(cat /tmp/carrier2.pid); if [ $? -eq 0 ]; then carrier2 -c /tmp/config.yaml -u -d; else carrier2 -c /tmp/config.yaml -d; fi"  # noqa
