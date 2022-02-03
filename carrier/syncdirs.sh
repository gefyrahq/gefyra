#!/bin/busybox sh
# vim:sw=4:ts=4:et

STOWAWAY_SVC="rsync://gefyra-stowaway-rsync.gefyra.svc.cluster.local:10873/carrier/"
PREFIX=$1

shift
# iterate all given directories to sync
for i in $@
do
    echo "Syncing: "$i
    busybox sh syncdir.sh $PREFIX $STOWAWAY_SVC $i &>/dev/null &
done