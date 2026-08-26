FROM public.ecr.aws/docker/library/debian:bookworm-slim@sha256:4724b8cc51e33e398f0e2e15e18d5ec2851ff0c2280647e1310bc1642182655d

WORKDIR /app

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
    asciinema=2.2.0-1 \
    ca-certificates \
    python3 \
    python3-pip \
    python3-venv \
    tmux=3.3a-3 \
    util-linux \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.lock /tmp/requirements.lock
RUN python3 -m venv /opt/verifier-venv \
 && /opt/verifier-venv/bin/pip install --no-cache-dir --require-hashes --no-deps \
    -r /tmp/requirements.lock

COPY Makefile /app/
COPY README.md /app/README.md
COPY bin /app/bin
COPY lib /app/lib
COPY data /app/data
COPY docs /app/docs
COPY helpers /app/helpers
COPY policies /app/policies
COPY scripts /app/scripts

RUN mkdir -p /opt/verifier-scripts \
 && install -m 0755 /app/scripts/rebuild-habitat-resupply /opt/verifier-scripts/rebuild-habitat-resupply \
 && bash /app/scripts/build.sh \
 && mkdir -p /app/state /app/output

ENV PATH="/app/bin:/opt/verifier-scripts:/opt/verifier-venv/bin:${PATH}"
