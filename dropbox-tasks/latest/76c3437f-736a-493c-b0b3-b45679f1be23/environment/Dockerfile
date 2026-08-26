FROM public.ecr.aws/docker/library/node:22-bookworm-slim@sha256:f3a68cf41a855d227d1b0ab832bed9749469ef38cf4f58182fb8c893bc462383

ENV NODE_ENV=production
WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-venv ca-certificates tmux asciinema \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv /opt/verifier \
    && /opt/verifier/bin/pip install --no-cache-dir --upgrade pip==25.1.1 \
    && /opt/verifier/bin/pip install --no-cache-dir pytest==8.4.1 requests==2.32.3 pytest-json-ctrf==0.3.5

ENV PATH="/opt/verifier/bin:${PATH}"

COPY package.json /app/package.json
COPY safari_runtime.md /app/safari_runtime.md
COPY safari_dispatch.mjs /app/safari_dispatch.mjs
COPY src /app/src
