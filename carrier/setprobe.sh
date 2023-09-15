#!/bin/busybox sh
# vim:sw=4:ts=4:et

set -e

DEFAULT_CONF_FILE="/tmp/nginx.conf"


echo "Setting listening port to $1 for probe"
block="server {listen $1 default; location / {return 200;}}\n#HTTPMARKER"
sed -i "s~#HTTPMARKER~$block~g" $DEFAULT_CONF_FILE

nginx -s reload -c $DEFAULT_CONF_FILE