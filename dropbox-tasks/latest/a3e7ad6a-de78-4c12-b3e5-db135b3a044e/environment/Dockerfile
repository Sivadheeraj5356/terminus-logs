FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac

WORKDIR /app

# Base image already ships python3. Skip apt python3-pip/python3-venv — some
# build proxies block python3-setuptools-whl (Executable Files category).
RUN apt-get update && apt-get install -y --no-install-recommends \
    asciinema \
    ca-certificates \
    tmux \
 && rm -rf /var/lib/apt/lists/*

RUN python3 -c "import urllib.request; urllib.request.urlretrieve('https://bootstrap.pypa.io/get-pip.py', '/tmp/get-pip.py')" \
 && python3 /tmp/get-pip.py --break-system-packages \
 && python3 -m pip install --break-system-packages virtualenv \
 && python3 -m virtualenv /opt/verifier-venv \
 && /opt/verifier-venv/bin/pip install --no-cache-dir \
    pytest==9.0.3 \
    pytest-json-ctrf==0.5.0 \
 && rm -f /tmp/get-pip.py

COPY go.mod ./
COPY cmd ./cmd
COPY internal ./internal
COPY scripts ./scripts
COPY docs ./docs
COPY fixtures ./fixtures
COPY verifier-fixtures/odip-holdout /opt/verifier-fixtures/odip-holdout
COPY verifier-fixtures/odip-holdout-seal /opt/verifier-fixtures/odip-holdout-seal
COPY verifier-fixtures/odip-holdout-slot /opt/verifier-fixtures/odip-holdout-slot

RUN mkdir -p /app/bin /app/state/odip/scratch /app/output/scratch \
 && CGO_ENABLED=0 go build -o /app/bin/odip ./cmd/odip

ENV PATH="/app/bin:${PATH}"
