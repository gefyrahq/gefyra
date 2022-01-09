FROM linuxserver/wireguard

ARG ADDRESS
ARG PRIVATE_KEY
ARG DNS
ARG PUBLIC_KEY
ARG ENDPOINT
ARG ALLOWED_IPS

RUN echo '[Interface] \n\
Address = '"$ADDRESS"' \n\
PrivateKey = '"$PRIVATE_KEY"' \n\
DNS = '"$DNS"' \n\
PreUp = sysctl -w net.ipv4.ip_forward=1 \n\
\n\
[Peer] \n\
PublicKey = '"$PUBLIC_KEY"' \n\
Endpoint = '"$ENDPOINT"' \n\
PersistentKeepalive = 21 \n\
AllowedIPs = '"$ALLOWED_IPS" > /config/wg0.conf

RUN cat /config/wg0.conf