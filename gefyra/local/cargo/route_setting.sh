#!/bin/sh

CONTAINER=$1
IP=$2

pid=$(sudo docker inspect -f '{{.State.Pid}}' $CONTAINER)
sudo mkdir -p /var/run/netns
sudo ln -s /proc/$pid/ns/net /var/run/netns/$pid
sudo ip netns exec $pid ip route del default
sudo ip netns exec $pid ip route add default via $IP