FROM linuxserver/wireguard

RUN apt update && apt install -y rsync docker.io cron

RUN mkdir /rsync
COPY syncdown.conf /etc/syncdown.conf
COPY syncjob.sh syncjob.sh
RUN chmod +x syncjob.sh

COPY sync-crontab /etc/cron.d/sync-crontab
RUN chmod 0644 /etc/cron.d/sync-crontab
RUN crontab /etc/cron.d/sync-crontab
RUN touch /var/log/cron.log

COPY 40-cron /etc/cont-init.d
