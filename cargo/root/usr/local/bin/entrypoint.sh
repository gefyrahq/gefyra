#!/bin/sh

/usr/bin/wg-gefyra up /config/wg0.conf
exec "$@"
sleep infinity