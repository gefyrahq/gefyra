#!/bin/busybox sh
# vim:sw=4:ts=4:et

set -e

DEFAULT_CONF_FILE="/tmp/nginx.conf"

# $1 is the listening port
# $2 is the user upstream
# $3 is the cluster upstream
# If header X-Gefyra-Bridge-Traffic is True, then the request is sent to the user upstream, otherwise it is sent to the cluster upstream.

echo "Setting listening port to $1; Setting target upstream to $2 and $3"
block="upstream gefyra_user_upstream { server $2; } upstream cluster_upstream { server $3; } map \$http_x_gefyra_bridge_traffic \$gefyra_backend { \\"True\\"  gefyra_user_upstream; default  cluster_upstream; }server {listen $1; location \/ { proxy_pass http:\/\/\$gefyra_backend;proxy_pass_request_headers  on;proxy_set_header Host \$host;}}\n#HTTPMARKER"
sed -i "s/#HTTPMARKER/$block/g" $DEFAULT_CONF_FILE

nginx -s reload -c $DEFAULT_CONF_FILE