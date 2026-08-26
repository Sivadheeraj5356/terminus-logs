FROM public.ecr.aws/docker/library/node:22-bookworm-slim@sha256:f3a68cf41a855d227d1b0ab832bed9749469ef38cf4f58182fb8c893bc462383

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        python3 \
        python3-pip \
        openssl \
        bash \
        ca-certificates \
        tmux \
        asciinema \
    && rm -rf /var/lib/apt/lists/* \
    && pip3 install --no-cache-dir --break-system-packages pytest==8.4.1

WORKDIR /app
COPY codebase/ /app/
RUN chmod +x /app/checks/smoke.sh /app/checks/format.sh
