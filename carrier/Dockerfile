FROM nginx:alpine
LABEL maintainer="Gefyra"
LABEL gefyra.dev/app="carrier"
LABEL gefyra.dev/role="bridge"
LABEL gefyra.dev/provider="carrier"

RUN apk add inotify-tools

COPY --chown=1000:1000 gefyra-carrier.conf /tmp/nginx.conf
COPY setroute.sh setroute.sh
COPY setprobe.sh setprobe.sh
COPY entrypoint.sh /
ENTRYPOINT ["/entrypoint.sh"]
RUN ln -sf /entrypoint.sh /bin/sh \
    && ln -sf /entrypoint.sh /bin/bash \
    && ln -sf /entrypoint.sh /bin/zsh \
    && ln -sf /entrypoint.sh /bin/ash
