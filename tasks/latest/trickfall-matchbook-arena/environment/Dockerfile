FROM public.ecr.aws/docker/library/debian:bookworm-slim@sha256:4724b8cc51e33e398f0e2e15e18d5ec2851ff0c2280647e1310bc1642182655d

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_ROOT_USER_ACTION=ignore \
    PYTHONDONTWRITEBYTECODE=1

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        asciinema \
        ca-certificates \
        python-is-python3 \
        python3 \
        python3-pip \
        rustc \
        tmux \
    && rm -rf /var/lib/apt/lists/*

RUN python -m pip install --no-cache-dir --break-system-packages --ignore-installed \
        iniconfig==2.3.0 \
        packaging==26.2 \
        pluggy==1.6.0 \
        pygments==2.20.0 \
        pytest==8.4.1 \
        pytest-json-ctrf==0.3.5

WORKDIR /app/matchbook
COPY matchbook/spec.md /app/matchbook/spec.md

LABEL org.opencontainers.image.source="trickfall-matchbook-engine" \
      org.opencontainers.image.revision="endgame-arena-2026-07-17" \
      org.opencontainers.image.created="2026-07-17T00:00:00Z" \
      org.opencontainers.image.version="2.0.0" \
      org.opencontainers.image.licenses="UNLICENSED"
