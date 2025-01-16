#!/bin/busybox sh
# vim:sw=4:ts=4:et

set -e

DEFAULT_CONF_FILE="/tmp/nginx.conf"

# $1 is the listening port
# $2 is the user upstream
# $3 is the cluster upstream
# If header X-Gefyra-Bridge-Traffic is True, then the request is sent to the user upstream, otherwise it is sent to the cluster upstream.

echo "Setting listening port to $1; Setting target upstream to $2"
block="map $http_x_gefyra_bridge_traffic $gefyra_backend { \"True\"  $2; default  $3; }server {listen $1; proxy_pass http://$gefyra_backend;}\n#MARKER"
sed -i "s/#MARKER/$block/g" $DEFAULT_CONF_FILE

nginx -s reload -c $DEFAULT_CONF_FILE