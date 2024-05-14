#!/bin/busybox sh
# vim:sw=4:ts=4:et

set -e

DEFAULT_CONF_FILE="/tmp/nginx.conf"


if [ -f /tmp/probesset_$1 ]; then
    echo "Probe already set to $1"
    exit 0
fi

echo "Setting listening port to $1 for probe"
block="server {listen $1 default; location / {return 200;}}\n#HTTPMARKER"
sed -i "s~#HTTPMARKER~$block~g" $DEFAULT_CONF_FILE

touch /tmp/probesset_$1

nginx -s reload -c $DEFAULT_CONF_FILE