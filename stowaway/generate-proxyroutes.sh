#!/bin/sh
# vim:sw=4:ts=4:et

set -e

DEFAULT_CONF_FILE="/etc/nginx/nginx.conf"
INPUT_DIRECTORY=$1

echo "worker_processes  auto;

error_log  /var/log/nginx/error.log notice;
pid        /tmp/nginx.pid;


events {
    worker_connections  1024;
}
" > $DEFAULT_CONF_FILE

gen_server_block () {
    echo "  server {
          listen $1;
          proxy_pass $2;
         }
         " >> $DEFAULT_CONF_FILE
}

echo "stream {
     " >> $DEFAULT_CONF_FILE
echo "Reading in: $INPUT_DIRECTORY"
for filename in $(ls $INPUT_DIRECTORY);
do
    echo "Generating $filename ..."
    route=($(cat $INPUT_DIRECTORY/$filename | tr "," " "))
    gen_server_block ${route[1]} ${route[0]}
done
echo "}" >> $DEFAULT_CONF_FILE

nginx -s reload