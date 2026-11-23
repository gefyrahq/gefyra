ARG ARCH=
ARG GOLANG_VERSION=1.24
ARG ALPINE_VERSION=3.20

FROM ${ARCH}golang:${GOLANG_VERSION}-alpine${ALPINE_VERSION} AS builder

ARG wg_go_tag=0.0.20250522
ARG wg_tools_tag=v1.0.20260223

RUN apk add --update git build-base libmnl-dev iptables

RUN git clone https://git.zx2c4.com/wireguard-go && \
    cd wireguard-go && \
    git checkout $wg_go_tag && \
    make && \
    make install

ENV WITH_WGQUICK=yes
RUN git clone https://git.zx2c4.com/wireguard-tools && \
    cd wireguard-tools && \
    git checkout $wg_tools_tag && \
    cd src && \
    make && \
    make install

FROM ghcr.io/linuxserver/baseimage-alpine:3.20
COPY --from=builder /usr/bin/wireguard-go /usr/bin/wg* /usr/bin/
COPY --from=builder /usr/bin/wg-quick /usr/bin/wg-gefyra

# set version label
ARG BUILD_DATE
ARG VERSION
ARG WIREGUARD_RELEASE
LABEL maintainer="Gefyra"
LABEL gefyra.dev/app="stowaway"
LABEL gefyra.dev/role="connection"
LABEL gefyra.dev/provider="stowaway"

ARG TARGETARCH
RUN \
  echo "**** install dependencies ****" && \
  apk add --no-cache --virtual=build-dependencies \
    build-base \
    elfutils-dev \
    gcc \
    git \
    linux-headers && \
  apk add --no-cache \
    bc \
    wget \
    coredns \
    inotify-tools \
    gnupg \
    grep \
    iproute2 \
    iptables \
    ip6tables \
    iputils \
    libcap-utils \
    libqrencode \
    net-tools \
    nginx \
    nginx-mod-stream \
    openresolv \
    python3 \
    perl \
    gettext-envsubst \
    tzdata && \
  ln -sf /dev/stdout /var/log/nginx/access.log && \
  ln -sf /dev/stderr /var/log/nginx/error.log && \
  mkdir -p /docker-entrypoint.d && \
  echo "**** clean up ****" && \
  apk del --no-network build-dependencies && \
  rm -rf \
    /tmp/*

# add local files
COPY /root /

# ports and volumes
EXPOSE 51820/udp
# for wireguard health check
EXPOSE 51822/tcp