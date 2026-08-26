FROM public.ecr.aws/docker/library/python:3.13-slim-bookworm@sha256:01f42367a0a94ad4bc17111776fd66e3500c1d87c15bbd6055b7371d39c124fb

WORKDIR /app

ENV DEBIAN_FRONTEND=noninteractive
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8
ENV PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
ENV CABAL_DIR=/var/cache/cabal

RUN apt-get update && apt-get install -y --no-install-recommends \
    tmux=3.3a-3 \
    asciinema=2.2.0-1 \
    jq=1.6-2.1+deb12u2 \
    ghc=9.0.2-4 \
    cabal-install=3.4.1.0-3 \
    libghc-aeson-dev=2.0.3.0-1+b5 \
    python3-pip \
    && rm -rf /var/lib/apt/lists/* \
    && tmux -V \
    && asciinema --version \
    && ghc --version \
    && cabal --version \
    && mkdir -p /var/cache/cabal

# Pre-seed an empty local Hackage index so `cabal build --offline` never
# attempts HTTP under Harbor allow_internet=false.
RUN mkdir -p /var/cache/cabal/packages/hackage.haskell.org \
    && tar -cf /var/cache/cabal/packages/hackage.haskell.org/00-index.tar -T /dev/null \
    && printf '%s\n' \
         'repository hackage.haskell.org' \
         '  url: http://hackage.haskell.org/' \
         '  secure: False' \
         '' \
         'remote-repo-cache: /var/cache/cabal/packages' \
         'world-file: /var/cache/cabal/world' \
         'extra-prog-path: /var/cache/cabal/bin' \
         'store-dir: /var/cache/cabal/store' \
         'jobs: $ncpus' \
         > /var/cache/cabal/config

COPY requirements.txt /tmp/requirements.txt
COPY requirements.lock /tmp/requirements.lock
RUN python3 -m pip install --no-cache-dir --break-system-packages \
    --require-hashes --no-deps -r /tmp/requirements.lock \
    && rm -f /tmp/requirements.txt /tmp/requirements.lock

COPY cabal.project /app/cabal.project
COPY cabal.project.local /app/cabal.project.local
COPY packages /app/packages
COPY keelmark-policy /app/keelmark-policy
COPY keelmark-ledger /app/keelmark-ledger
COPY keelmark-shards /app/keelmark-shards
COPY docs /app/docs
COPY scripts /app/scripts
COPY keelmark.sh /app/keelmark.sh
COPY README.md /app/README.md
COPY CHANGELOG.md /app/CHANGELOG.md

RUN chmod +x /app/keelmark.sh /app/scripts/*.sh \
    && mkdir -p /app/output /app/bin /app/dist-newstyle

LABEL org.opencontainers.image.source="https://github.com/snorkel-ai/harbor"
LABEL org.opencontainers.image.description="Keelmark Haskell Cabal keel-block load packaging console for Project Terminus"
LABEL org.opencontainers.image.created="2026-07-18T00:00:00Z"
LABEL org.opencontainers.image.revision="1"
LABEL org.opencontainers.image.version="1.0"
LABEL org.opencontainers.image.licenses="MIT"

ENTRYPOINT []
CMD ["sleep", "infinity"]
