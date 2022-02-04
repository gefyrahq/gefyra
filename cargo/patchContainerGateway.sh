#!/bin/sh

CONTAINER=$1
IP=$2

pid=$(docker inspect -f '{{.State.Pid}}' $CONTAINER)
mkdir -p /var/run/netns
ln -s /proc/$pid/ns/net /var/run/netns/$pid
ip netns exec $pid ip route del default
ip netns exec $pid ip route add default via $IP