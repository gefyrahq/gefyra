FROM ubuntu
# run a server on port 8000
RUN apt update && apt install -y iproute2 iputils-ping python3 traceroute wget curl
COPY local.py local.py
CMD python3 local.py