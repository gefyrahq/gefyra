ARG ARCH=
ARG GOLANG_VERSION=1.17.6
ARG ALPINE_VERSION=3.15

FROM ${ARCH}golang:${GOLANG_VERSION}-bullseye as builder

ARG go_tag=0.0.20220117
ARG tools_tag=v1.0.20210914

RUN  apt-get update && \
 apt-get install -y --no-install-recommends \
 git \
 build-essential \
 libmnl-dev \
 iptables

RUN git clone https://git.zx2c4.com/wireguard-go && \
    cd wireguard-go && \
    git checkout $go_tag && \
    make && \
    make install

ENV WITH_WGQUICK=yes
RUN git clone https://git.zx2c4.com/wireguard-tools && \
    cd wireguard-tools && \
    git checkout $tools_tag && \
    cd src && \
    make && \
    make install

FROM ghcr.io/linuxserver/baseimage-ubuntu:bionic
COPY --from=builder /usr/bin/wireguard-go /usr/bin/wg* /usr/bin/
COPY --from=builder /usr/bin/wg-quick /usr/bin/

# set version label
ARG BUILD_DATE
ARG VERSION
ARG WIREGUARD_RELEASE
LABEL maintainer="Schille"

ENV DEBIAN_FRONTEND="noninteractive"

RUN \
 echo "**** install dependencies ****" && \
 apt-get update && \
 apt-get install -y --no-install-recommends \
	bc \
	curl \
	gnupg \
	ifupdown \
	iproute2 \
	iptables \
	iputils-ping \
	jq \
	net-tools \
	openresolv \
	pkg-config \
    rsync \
    docker.io \
    cron && \
 echo "**** clean up ****" && \
 rm -rf \
	/tmp/* \
	/var/lib/apt/lists/* \
	/var/tmp/*
# add local files
COPY /root /

RUN mkdir /rsync
RUN chmod +x /syncjob.sh

RUN chmod 0644 /etc/cron.d/sync-crontab \
  && crontab /etc/cron.d/sync-crontab \
  && touch /var/log/cron.log

# This might be required for Windows
# RUN patch /usr/bin/wg-quick /wgquick.patch
