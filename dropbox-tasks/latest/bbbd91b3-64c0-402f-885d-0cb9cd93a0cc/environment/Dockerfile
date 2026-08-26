FROM public.ecr.aws/docker/library/rust:1.85-slim@sha256:9f841bbe9e7d8e37ceb96ed907265a3a0df7f44e3737d0b100e7907a679acb36

LABEL org.opencontainers.image.source="harbor-tb3/tasks/chess-threefold-repetition-position-key-repair" \
      org.opencontainers.image.version="2.0" \
      org.opencontainers.image.created="2026-06-28T00:00:00Z" \
      org.opencontainers.image.licenses="UNLICENSED" \
      org.opencontainers.image.title="chess-threefold-repetition-position-key-repair"

RUN apt-get update && apt-get install -y --no-install-recommends \
        tmux=3.3a-3 \
        asciinema=2.2.0-1 \
        python3=3.11.2-1+b1 \
        python3-venv=3.11.2-1+b1 \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv /opt/verifier \
    && /opt/verifier/bin/pip install --no-cache-dir \
        pytest==8.4.1 \
        pytest-json-ctrf==0.3.5

ENV PATH=/opt/verifier/bin:${PATH}

WORKDIR /app

COPY Cargo.toml Cargo.lock /app/environment/
COPY docs/ /app/environment/docs/
COPY fixtures/ /app/environment/fixtures/
COPY scripts/ /app/environment/scripts/
COPY h1/ /app/environment/h1/
COPY m2/ /app/environment/m2/
COPY q7m/ /app/environment/q7m/
COPY r3/ /app/environment/r3/

RUN bash /app/environment/scripts/build_q7m.sh
