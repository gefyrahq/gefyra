import textwrap

RELOAD_CARRIER2 = "kill -SIGQUIT $(ps | grep '[c]arrier2' | awk ' { print $1 }' | tail -1) && carrier2 -c /tmp/config.yaml -u &"  # noqa

CARRIER2_CONFIG_TEMPLATE = textwrap.dedent(
    """
---
version: 1
threads: 4
pid_file: /tmp/carrier2.pid
error_log: /tmp/carrier.error.log
upgrade_sock: /tmp/carrier2.sock
upstream_keepalive_pool_size: 100
port: {container_port}
clusterUpstream:
    - \"{ip}:{destination_port}\"
"""
)
