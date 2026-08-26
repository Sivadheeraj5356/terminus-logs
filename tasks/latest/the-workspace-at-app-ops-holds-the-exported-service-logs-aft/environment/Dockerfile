FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac

ENV DEBIAN_FRONTEND=noninteractive
ENV TERM=xterm
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8
ENV PATH="/opt/verifier-venv/bin:/usr/local/go/bin:${PATH}"

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    asciinema \
    ca-certificates \
    jq \
    python3 \
    python3-venv \
    sqlite3 \
    tmux \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /var/tmp/tmux /app/output

RUN python3 -m venv /opt/verifier-venv \
    && /opt/verifier-venv/bin/pip install --no-cache-dir \
        pytest==8.4.1 \
        pytest-json-ctrf==0.3.5

COPY go.mod /app/environment/go.mod
COPY cmd /app/environment/cmd
RUN /usr/local/go/bin/go build -C /app/environment -o /usr/local/bin/rotlogctl /app/environment/cmd/rotlogctl

COPY docs /app/environment/docs
COPY fixtures/ops /app/ops
COPY fixtures/ledger_seed.sql /app/environment/fixtures/ledger_seed.sql
RUN mkdir -p /app/ops/state \
    && sqlite3 /app/ops/state/export_ledger.sqlite < /app/environment/fixtures/ledger_seed.sql \
    && chmod 0644 /app/ops/state/export_ledger.sqlite

WORKDIR /app
