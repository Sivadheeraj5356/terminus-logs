# Single-stage canonical Go image: agents compile /app/carrydown_engine during debugging.
# tmux and asciinema are required by the agent runtime.
FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac

ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=UTC
ENV PATH="/usr/local/go/bin:/go/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
ENV GOFLAGS=-mod=mod
ENV GOTOOLCHAIN=local
ENV GOCACHE=/tmp/go-cache
ENV GOPATH=/tmp/go
ENV PYTHONDONTWRITEBYTECODE=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
ENV PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        asciinema \
        ca-certificates \
        python-is-python3 \
        python3=3.11.2-1+b1 \
        python3-pip \
        tmux \
    && ln -sf /usr/bin/python3 /usr/bin/python \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /opt/verifier/wheels /app/bin /app/output

COPY requirements.lock /opt/verifier/requirements.lock
COPY wheels/ /opt/verifier/wheels/

RUN python3 -m pip install --no-cache-dir --break-system-packages --no-index \
    --find-links /opt/verifier/wheels \
    --require-hashes --no-deps -r /opt/verifier/requirements.lock

WORKDIR /app

COPY carrydown_engine/ /app/carrydown_engine/
COPY pledge_inputs/ /app/pledge_inputs/
COPY billing_contracts/ /app/billing_contracts/
COPY rebuild.sh /app/rebuild.sh

RUN chmod +x /app/rebuild.sh \
    && mkdir -p /app/output /app/bin \
    && chmod -R a-w /app/pledge_inputs /app/billing_contracts
