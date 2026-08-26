FROM public.ecr.aws/docker/library/node:22-bookworm-slim@sha256:f3a68cf41a855d227d1b0ab832bed9749469ef38cf4f58182fb8c893bc462383

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        asciinema \
        ca-certificates \
        python3 \
        python3-pip \
        tmux \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m pip install --no-cache-dir --break-system-packages \
        cryptography==46.0.0 \
        duckdb==1.4.3 \
        pytest==8.4.1 \
        pytest-json-ctrf==0.3.5

WORKDIR /app
COPY app/package.json app/package-lock.json ./
RUN npm ci --omit=dev --ignore-scripts=false \
    && npm cache clean --force

COPY app/ /app/
RUN chmod 0755 /app/bin/pfseal-worker

CMD ["/bin/bash"]
