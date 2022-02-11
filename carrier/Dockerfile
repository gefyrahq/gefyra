FROM nginx:alpine
LABEL maintainer="Gefyra"

RUN apk add rsync inotify-tools
COPY gefyra-carrier.conf /etc/nginx/nginx.conf
COPY setroute.sh setroute.sh
COPY syncdirs.sh syncdirs.sh
COPY syncdir.sh syncdir.sh
COPY setprobe.sh setprobe.sh
COPY entrypoint.sh /
ENTRYPOINT ["/entrypoint.sh"]
RUN ln -sf /entrypoint.sh /bin/sh \
    && ln -sf /entrypoint.sh /bin/bash \
    && ln -sf /entrypoint.sh /bin/zsh \
    && ln -sf /entrypoint.sh /bin/ash && \
    chmod 777 /etc/nginx/ && \
    chgrp -R root /var/cache/nginx /var/run /var/log/nginx && \
    chmod -R 770 /var/cache/nginx /var/run /var/log/nginx

