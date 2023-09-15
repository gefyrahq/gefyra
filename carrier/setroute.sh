#!/bin/busybox sh
# vim:sw=4:ts=4:et

set -e

DEFAULT_CONF_FILE="/tmp/nginx.conf"


echo "Setting listening port to $1; Setting target upstream to $2"
block="upstream stowaway-$1 {server $2;} server {listen $1; proxy_pass stowaway-$1;}\n#MARKER"
sed -i "s/#MARKER/$block/g" $DEFAULT_CONF_FILE

nginx -s reload -c $DEFAULT_CONF_FILE