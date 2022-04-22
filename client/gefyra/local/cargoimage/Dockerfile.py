# flake8: noqa
import io
import sys


def get_dockerfile(cargo_image):
    if sys.platform == "win32":
        return io.BytesIO(
            f""" 
FROM {cargo_image}
RUN patch /usr/bin/wg-quick /wgquick.patch

ARG ADDRESS
ARG PRIVATE_KEY
ARG DNS
ARG PUBLIC_KEY
ARG ENDPOINT
ARG ALLOWED_IPS

RUN echo '[Interface] \\n\
Address = '"$ADDRESS"' \\n\
PrivateKey = '"$PRIVATE_KEY"' \\n\
DNS = '"$DNS"' \\n\
PreUp = sysctl -w net.ipv4.ip_forward=1 \\n\
PostUp = iptables -A FORWARD -i %i -j ACCEPT; iptables -A FORWARD -o %i -j ACCEPT; iptables -t nat -A POSTROUTING -o eth1 -j MASQUERADE \\n\ 
PostDown = iptables -D FORWARD -i %i -j ACCEPT; iptables -D FORWARD -o %i -j ACCEPT; iptables -t nat -D POSTROUTING -o eth1 -j MASQUERADE \\n\
\\n\
[Peer] \\n\
PublicKey = '"$PUBLIC_KEY"' \\n\
Endpoint = '"$ENDPOINT"' \\n\
PersistentKeepalive = 21 \\n\
AllowedIPs = '"$ALLOWED_IPS" > /config/wg0.conf

RUN cat /config/wg0.conf
""".encode(
                "utf-8"
            )
        )
    else:
        return io.BytesIO(
            f""" 
FROM {cargo_image}

ARG ADDRESS
ARG PRIVATE_KEY
ARG DNS
ARG PUBLIC_KEY
ARG ENDPOINT
ARG ALLOWED_IPS

RUN echo '[Interface] \\n\
Address = '"$ADDRESS"' \\n\
PrivateKey = '"$PRIVATE_KEY"' \\n\
DNS = '"$DNS"' \\n\
PreUp = sysctl -w net.ipv4.ip_forward=1 \\n\
PostUp = iptables -A FORWARD -i %i -j ACCEPT; iptables -A FORWARD -o %i -j ACCEPT; iptables -t nat -A POSTROUTING -o eth1 -j MASQUERADE \\n\ 
PostDown = iptables -D FORWARD -i %i -j ACCEPT; iptables -D FORWARD -o %i -j ACCEPT; iptables -t nat -D POSTROUTING -o eth1 -j MASQUERADE \\n\
\\n\
[Peer] \\n\
PublicKey = '"$PUBLIC_KEY"' \\n\
Endpoint = '"$ENDPOINT"' \\n\
PersistentKeepalive = 21 \\n\
AllowedIPs = '"$ALLOWED_IPS" > /config/wg0.conf

RUN cat /config/wg0.conf
        """.encode(
                "utf-8"
            )
        )
