FROM public.ecr.aws/docker/library/node:22-bookworm-slim@sha256:f3a68cf41a855d227d1b0ab832bed9749469ef38cf4f58182fb8c893bc462383
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3=3.11.2-1+b1 \
    python3-pip=23.0.1+dfsg-1 \
    tmux=3.3a-3 \
    asciinema=2.2.0-1 \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m pip install --no-cache-dir --break-system-packages \
    pytest==8.4.1 \
    pytest-json-ctrf==0.3.5

COPY . /app/environment/
RUN mkdir -p /app/out /app/tmp && \
    ln -sf /app/environment/h3 /app/h3 && \
    ln -sf /app/environment/k6 /app/k6 && \
    ln -sf /app/environment/p4 /app/p4 && \
    ln -sf /app/environment/z9 /app/z9 && \
    ln -sf /app/environment/config /app/config && \
    ln -sf /app/environment/data /app/data && \
    ln -sf /app/environment/docs /app/docs && \
    chmod +x /app/z9/w9_once.js /app/environment/scripts/bake_ref.sh && \
    bash /app/environment/scripts/bake_ref.sh && rm -f /app/environment/scripts/bake_ref.sh

CMD ["node", "-e", "console.log('ready')"]
