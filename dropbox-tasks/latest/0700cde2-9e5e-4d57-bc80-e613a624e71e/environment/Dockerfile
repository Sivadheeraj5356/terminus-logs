FROM public.ecr.aws/docker/library/debian:bookworm-slim@sha256:4724b8cc51e33e398f0e2e15e18d5ec2851ff0c2280647e1310bc1642182655d

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
    asciinema \
    ca-certificates \
    libdigest-sha-perl \
    libjson-pp-perl \
    perl \
    python3 \
    python3-pip \
    python3-venv \
    tmux \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.lock /tmp/requirements.lock
RUN python3 -m venv /opt/verifier-venv \
 && /opt/verifier-venv/bin/pip install --no-cache-dir --require-hashes -r /tmp/requirements.lock \
 && rm -f /tmp/requirements.lock

WORKDIR /app

COPY helpers/ ./helpers/
COPY scripts/ ./scripts/
COPY lib/ ./lib/
COPY docs/ ./docs/
COPY spec/ ./spec/
COPY lattice-invariant-catalog/ ./lattice-invariant-catalog/
COPY conching-network/ ./conching-network/
COPY kiln-run-traces/ ./kiln-run-traces/
COPY var/ ./var/

RUN mkdir -p /app/state /app/output /app/bin \
 && install -m 755 /app/scripts/polymorph-chronicle /app/bin/polymorph-chronicle

ENV PATH="/opt/verifier-venv/bin:/app/bin:${PATH}"
ENV PERL5LIB="/app/lib"
