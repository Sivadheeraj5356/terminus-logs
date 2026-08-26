FROM public.ecr.aws/docker/library/node:22-bookworm-slim@sha256:f3a68cf41a855d227d1b0ab832bed9749469ef38cf4f58182fb8c893bc462383

RUN apt-get update && apt-get install -y --no-install-recommends \
    asciinema \
    python3 \
    python3-pip \
    python3-venv \
    tmux \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY repo/package.json ./package.json
RUN npm install --omit=dev
COPY repo/ ./

COPY requirements.lock /tmp/requirements.lock
RUN python3 -m venv /opt/verifier && /opt/verifier/bin/pip install --no-cache-dir -r /tmp/requirements.lock
ENV PATH="/opt/verifier/bin:${PATH}"
