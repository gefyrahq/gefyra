#!/bin/bash
# vim:sw=4:ts=4:et

set -e
BASEPATH="/rsync"
CONFIG_FILE="/etc/syncdown.conf"
RSYNC_SVC="rsync://192.168.99.1:10873/carrier"

grep -v -e "^#" -e "^$" $CONFIG_FILE | while IFS= read -r line
do
  #container name;bridge name;prefix;relative directory;target directory
  IFS=";" read -r -a arr <<< "${line}"
  local_container="${arr[1]}"
  bridge_name="${arr[0]}"
  prefix="${arr[2]}"
  relative_path="${arr[3]}"
  target_dir="${arr[4]}"
  echo $local_container
  echo $bridge_name
  echo $prefix
  echo $relative_path
  echo $target_dir
  mkdir -p $BASEPATH/$prefix
  cd $BASEPATH/$prefix
  rsync -avz $RSYNC_SVC/$prefix .
  docker exec $local_container mkdir -p $target_dir
  docker cp $relative_path $local_container:$target_dir
done