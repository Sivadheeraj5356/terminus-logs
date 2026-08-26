FROM public.ecr.aws/docker/library/node:22-bookworm-slim@sha256:f3a68cf41a855d227d1b0ab832bed9749469ef38cf4f58182fb8c893bc462383

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        python3=3.11.2-1+b1 \
        python3-pip=23.0.1+dfsg-1 \
        patch=2.7.6-7 \
        tmux=3.3a-3 \
        asciinema=2.2.0-1 \
    && rm -rf /var/lib/apt/lists/*

RUN pip3 install --no-cache-dir --break-system-packages \
    pytest==8.4.1 \
    pytest-json-ctrf==0.3.5 \
    pytest-randomly==3.16.0

WORKDIR /app
COPY . /app/environment/
RUN cp -r /app/environment/docs /app/docs
RUN chmod +x /app/environment/cli/driver.mjs
