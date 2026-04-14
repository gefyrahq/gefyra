#!/bin/sh

# Invoke wg-quick via explicit bash (not kernel-shebang exec) to work around
# a host-side EACCES on Docker 29 / Ubuntu 25.10 where a bash process started
# via kernel-shebang exec cannot exec further binaries.
/bin/bash /usr/bin/wg-quick up /config/wg0.conf

trap '/bin/bash /usr/bin/wg-quick down /config/wg0.conf; exit 0' TERM INT

if [ "$#" -gt 0 ]; then
    "$@" &
    wait $!
else
    sleep infinity &
    wait $!
fi
