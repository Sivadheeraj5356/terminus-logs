FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        asciinema \
        python3 \
        python3-pip \
        python3-venv \
        tmux \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.lock /tmp/requirements.lock
RUN python3 -m venv /opt/verifier-venv \
    && /opt/verifier-venv/bin/pip install --no-cache-dir -r /tmp/requirements.lock

WORKDIR /app
COPY go.mod README.md /app/
COPY docs /app/docs
COPY fixtures /app/fixtures
COPY verifier-fixtures /opt/verifier-fixtures
COPY scripts /app/scripts
COPY internal /app/internal
COPY cmd /app/cmd
RUN mkdir -p /app/bin /app/state \
    && chmod +x /app/scripts/verifier-rebuild.sh \
    && sed -i 's/\r$//' /app/scripts/*.sh \
    && go build -o /app/bin/helmvals ./cmd/helmvals
