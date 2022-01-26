FROM nginx:alpine
COPY gefyra-carrier.conf /etc/nginx/nginx.conf
COPY setroute.sh setroute.sh
COPY syncdirs.sh syncdirs.sh
COPY syncdir.sh syncdir.sh
RUN apk add rsync inotify-tools
