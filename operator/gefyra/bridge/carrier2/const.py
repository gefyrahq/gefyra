RELOAD_CARRIER2 = "kill -SIGQUIT $(ps | grep '[c]arrier2' | awk ' { print $1 }' | tail -1) && carrier2 -c /tmp/config.yaml -u &"  # noqa
