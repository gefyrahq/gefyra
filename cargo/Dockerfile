ARG ARCH=
ARG GOLANG_VERSION=1.18
ARG ALPINE_VERSION=3.17

FROM ${ARCH}golang:${GOLANG_VERSION}-alpine${ALPINE_VERSION} as builder

ARG wg_go_tag=0.0.20220316
ARG wg_tools_tag=v1.0.20210914

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

FROM ghcr.io/linuxserver/baseimage-alpine:3.17
COPY --from=builder /usr/bin/wireguard-go /usr/bin/wg* /usr/bin/
COPY --from=builder /usr/bin/wg-quick /usr/bin/

# set version label
ARG BUILD_DATE
ARG VERSION
ARG WIREGUARD_RELEASE
LABEL maintainer="Schille"

ARG TARGETARCH
RUN \
  echo "**** install dependencies ****" && \
  apk add --no-cache --virtual=build-dependencies \
    build-base \
    elfutils-dev \
    linux-headers && \
  apk add --no-cache \
    bc \
    wget \
    gnupg \
    grep \
    iproute2 \
    iptables \
    ip6tables \
    iputils \
    libcap-utils \
    libqrencode \
    net-tools \
    patch \
    openresolv \
    perl && \
  echo "**** clean up ****" && \
  apk del --no-network build-dependencies && \
  rm -rf \
    /tmp/*
    
# add local files
COPY /root /


# This might be required for Windows
# RUN patch /usr/bin/wg-quick /wgquick.patch
