#!/bin/sh

# Use explicit 'bash' to work around kernel 6.x overlayfs exec restriction
# where shebang-based exec of wg-quick causes child EACCES errors.
bash /usr/bin/wg-quick up /config/wg0.conf
exec "$@"
sleep infinity
