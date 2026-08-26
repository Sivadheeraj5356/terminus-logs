FROM public.ecr.aws/docker/library/gcc:13-bookworm@sha256:930f2ebe239275fa67226654cb79273ea34eee672ae61c8a39f689c37fb7ac5c AS verifier-builder

ENV DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8

WORKDIR /app

COPY wheels/ /opt/verifier-wheels/
COPY requirements.lock /tmp/requirements.lock

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      python3 \
      python3-pip \
      python3-venv && \
    python3 -m venv /opt/verifier-venv && \
    /opt/verifier-venv/bin/pip install \
      --no-cache-dir \
      --no-deps \
      --no-index \
      --only-binary=:all: \
      --find-links=/opt/verifier-wheels \
      --require-hashes \
      -r /tmp/requirements.lock && \
    /opt/verifier-venv/bin/pip check && \
    /opt/verifier-venv/bin/python -m pytest --version >/dev/null && \
    rm -rf /opt/verifier-wheels /tmp/requirements.lock /var/lib/apt/lists/*


FROM public.ecr.aws/docker/library/gcc:13-bookworm@sha256:930f2ebe239275fa67226654cb79273ea34eee672ae61c8a39f689c37fb7ac5c

LABEL org.opencontainers.image.title="Tidevault arena" \
      org.opencontainers.image.description="Offline stateful rotating-ring strategy game with a learned CPU opponent" \
      org.opencontainers.image.source="local://terminus/tidevault-arena" \
      org.opencontainers.image.revision="1" \
      org.opencontainers.image.created="2026-07-19T05:00:00Z" \
      org.opencontainers.image.version="1.0.0" \
      org.opencontainers.image.licenses="NOASSERTION"

ENV DEBIAN_FRONTEND=noninteractive \
    HOME=/tmp \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    TMPDIR=/tmp \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONHASHSEED=0

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      asciinema \
      python3 \
      tmux && \
    rm -rf /var/lib/apt/lists/*

COPY app/ /app/
COPY --from=verifier-builder /opt/verifier-venv/ /opt/verifier-venv/
COPY private/ /opt/arena-private/
COPY model/mid.tvnn /opt/arena-private/mid.tvnn
COPY difficulty_knobs.conf /opt/arena-private/difficulty_knobs.conf
COPY arena/healthcheck.sh /opt/arena-private/healthcheck.sh
COPY arena/bootstrap.sh /usr/local/sbin/arena-bootstrap

RUN chmod 0755 /app/arena && \
    chmod 0644 /app/README.md && \
    command -v g++ >/dev/null && \
    command -v python3 >/dev/null && \
    test -x /opt/verifier-venv/bin/python && \
    chmod 0700 \
      /opt/arena-private \
      /opt/verifier-venv \
      /opt/arena-private/healthcheck.sh \
      /usr/local/sbin/arena-bootstrap && \
    chmod 0600 \
      /opt/arena-private/core.py \
      /opt/arena-private/model.py \
      /opt/arena-private/search.py \
      /opt/arena-private/referee.py \
      /opt/arena-private/mid.tvnn \
      /opt/arena-private/difficulty_knobs.conf && \
    install -d -m 0755 /run/arena && \
    install -d -m 1777 /logs

HEALTHCHECK --interval=1s --timeout=3s --start-period=1s --retries=30 \
    CMD ["/opt/arena-private/healthcheck.sh"]

ENTRYPOINT ["/usr/local/sbin/arena-bootstrap"]
