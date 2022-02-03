#!/bin/busybox sh
# vim:sw=4:ts=4:et

PREFIX=$1
STOWAWAY_SVC=$2
SYNC_FOLDER=$3
rsync -avz --relative $SYNC_FOLDER/ $STOWAWAY_SVC$PREFIX/
while inotifywait -r -e modify,create,delete $SYNC_FOLDER
do
  rsync -avz --relative $SYNC_FOLDER/ $STOWAWAY_SVC$PREFIX/
done