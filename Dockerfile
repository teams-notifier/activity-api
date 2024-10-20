FROM python:slim-bookworm

LABEL org.opencontainers.image.source=https://github.com/teams-notifier/activity-api

WORKDIR /app

COPY requirements.txt /app/

RUN set -e \
    && useradd -ms /bin/bash -d /app app \
    && pip install --no-cache-dir -r /app/requirements.txt --break-system-packages

COPY . /app/

WORKDIR /app
USER app
CMD ["/app/run.sh"]
