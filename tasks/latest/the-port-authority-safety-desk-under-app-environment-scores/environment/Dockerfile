# Canonical Node.js runtime (Edition 2 / PLATFORM_AUTO_EVAL.md table).
FROM public.ecr.aws/docker/library/node:22-bookworm-slim@sha256:f3a68cf41a855d227d1b0ab832bed9749469ef38cf4f58182fb8c893bc462383

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3=3.11.2-1+b1 \
    python3-venv=3.11.2-1+b1 \
    sqlite3=3.40.1-2+deb12u2 \
    tmux=3.3a-3 \
    asciinema=2.2.0-1 \
    ca-certificates=20230311+deb12u1 \
    openssl=3.0.20-1~deb12u2 \
    libssl3=3.0.20-1~deb12u2 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /tmp/requirements.txt
RUN python3 -m venv /opt/verifier \
    && /opt/verifier/bin/pip install --no-cache-dir --require-hashes --no-deps -r /tmp/requirements.txt
ENV PATH=/opt/verifier/bin:${PATH}

WORKDIR /app

COPY package.json package-lock.json tsconfig.json /app/environment/
RUN cd /app/environment && npm ci --no-audit --no-fund

COPY README.md /app/environment/
COPY docs/ /app/environment/docs/
COPY fixtures/ /app/environment/fixtures/
COPY hold/ /app/environment/hold/
COPY j8r/ /app/environment/j8r/
COPY pilot/ /app/environment/pilot/
COPY q4n/ /app/environment/q4n/
COPY schemas/ /app/environment/schemas/
COPY tools/ /app/environment/tools/
COPY v2x/ /app/environment/v2x/
RUN cd /app/environment \
    && npm run build \
    && ln -sfn /app/environment/tools /app/tools \
    && chmod +x /app/environment/tools/k9ctl \
    && chmod +x /app/environment/hold/ref_hold.py \
    && mkdir -p /app/output/run_traces
