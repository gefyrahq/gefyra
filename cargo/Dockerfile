ARG ARCH=
ARG GOLANG_VERSION=1.18
ARG ALPINE_VERSION=3.17

FROM rust:slim-buster as udp2tcp-builder
RUN apt update && apt install wget unzip -y

ARG TARGETARCH
ARG UDP_OVER_TCP_VERSION=0.4.0

ENV UDP_OVER_TCP_VERSION=${UDP_OVER_TCP_VERSION}

RUN if [ "$TARGETARCH" = "arm64" ]; then \
      export RUST_TARGET=aarch64-unknown-linux-gnu; \
    elif [ "$TARGETARCH" = "amd64" ]; then \
      export RUST_TARGET=x86_64-unknown-linux-gnu; \
    else \
      echo "Unsupported target $TARGETARCH"; \
      exit 1; \
    fi && \
    rustup target add $RUST_TARGET && \
    wget https://github.com/mullvad/udp-over-tcp/archive/refs/tags/v${UDP_OVER_TCP_VERSION}.zip && \
    unzip v${UDP_OVER_TCP_VERSION}.zip && \
    cd /udp-over-tcp-${UDP_OVER_TCP_VERSION} && \
    RUSTFLAGS="-C target-feature=+crt-static" \
    cargo build --release \
    --target $RUST_TARGET \
    --features env_logger \
    --features clap \
    --features statsd \
    --bins

WORKDIR /udp-over-tcp-{$UDP_OVER_TCP_VERSION}

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

FROM alpine:3.17 as cargo
COPY --from=builder /usr/bin/wireguard-go /usr/bin/wg* /usr/bin/
COPY --from=builder /usr/bin/wg-quick /usr/bin/
COPY --from=udp2tcp-builder /udp-over-tcp-*/target/*/release/udp2tcp /usr/bin/

# set version label
ARG BUILD_DATE
ARG VERSION
ARG WIREGUARD_RELEASE
LABEL maintainer="Gefyra"
LABEL gefyra.dev/app="cargo"
LABEL gefyra.dev/role="connection"
LABEL gefyra.dev/provider="cargo"

ARG TARGETARCH
RUN \
  echo "**** install dependencies ****" && \
  apk add --no-cache --virtual=build-dependencies \
    build-base \
    elfutils-dev \
    linux-headers && \
  apk add --no-cache \
    bc \
    bash \
    wget \
    docker \
    gnupg \
    grep \
    iproute2 \
    iptables \
    ip6tables \
    iputils \
    libcap-utils \
    net-tools \
    patch \
    openresolv \
    && \
  echo "**** clean up ****" && \
  apk del --no-network build-dependencies && \
  rm -rf \
    /tmp/*
    
# add local files
COPY /root /
RUN chmod u+x,g+x /usr/local/bin/entrypoint.sh\
  && ln -s /usr/local/bin/entrypoint.sh / # backwards compat
RUN echo "net.ipv4.ip_forward=1" >> /etc/sysctl.conf
ENTRYPOINT ["entrypoint.sh"]

FROM cargo as cargo-win
RUN patch /usr/bin/wg-quick /wgquick.patch
