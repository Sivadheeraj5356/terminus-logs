FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac

WORKDIR /app

# Avoid apt python3-venv/python3-pip: some build proxies block python3-setuptools-whl.
RUN apt-get update && apt-get install -y --no-install-recommends \
    asciinema \
    ca-certificates \
    curl \
    tmux \
 && rm -rf /var/lib/apt/lists/*

RUN python3 -c "import venv; venv.create('/opt/verifier-venv', with_pip=False, clear=True)" \
 && curl -fsSL https://bootstrap.pypa.io/get-pip.py -o /tmp/get-pip.py \
 && /opt/verifier-venv/bin/python /tmp/get-pip.py \
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
COPY trusted_roots.json ./

RUN mkdir -p /app/bin /app/state/pki-evidence /app/output \
 && go build -o /app/bin/ctpki ./cmd/ctpki \
 && chmod +x /app/scripts/pki_migration_bundle_gate.sh

ENV PATH="/app/bin:${PATH}"
