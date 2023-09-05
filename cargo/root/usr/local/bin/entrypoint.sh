#!/bin/sh

/usr/bin/wg-quick up /config/wg0.conf
exec "$@"
sleep infinity