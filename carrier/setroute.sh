#!/bin/sh
# vim:sw=4:ts=4:et

set -e

DEFAULT_CONF_FILE="/etc/nginx/nginx.conf"


echo "Setting listening port to $1"
sed -i "s/listen 8080;/listen $1;/g" $DEFAULT_CONF_FILE

echo "Setting target upstream to $2"
sed -i "s/server 127.0.0.1:9999;/server $2;/g" $DEFAULT_CONF_FILE

nginx -s reload