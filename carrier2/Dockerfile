# Use a Rust base image with Cargo installed
FROM rust:latest AS builder
RUN apt update && apt install -y cmake clang musl musl-tools
# this is a current workaround as musl-g++ is not found by Cmake
RUN ln -s /bin/g++ /bin/musl-g++

# Set the working directory inside the container
WORKDIR /carrier

# Copy the Cargo.toml and Cargo.lock files
COPY Cargo.toml Cargo.lock ./
# Now copy the source code
COPY ./src ./src
COPY ./benches ./benches

# Build your application
RUN rustup target add x86_64-unknown-linux-musl
RUN cargo build --release --target=x86_64-unknown-linux-musl


## -- Production --
FROM busybox:latest
LABEL maintainer="Gefyra"
LABEL gefyra.dev/app="carrier2"
LABEL gefyra.dev/role="bridge"
LABEL gefyra.dev/provider="carrier2"

# Copy the statically linked binary
COPY --from=builder /carrier/target/x86_64-unknown-linux-musl/release/carrier2 /bin/carrier2
# Add default config
COPY config.yaml /tmp/config.yaml
COPY entrypoint.sh /entrypoint.sh
COPY etc/ /etc
RUN touch /tmp/carrier.error.log && touch /tmp/carrier2.sock


RUN ln -sf /entrypoint.sh /bin/sh \
    && ln -sf /entrypoint.sh /bin/bash \
    && ln -sf /entrypoint.sh /bin/zsh \
    && ln -sf /entrypoint.sh /bin/ash
CMD ["busybox", "init"]