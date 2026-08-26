# Canonical final runtime base per docs/PLATFORM_AUTO_EVAL.md (Jun 2026 list):
# rust:1.85-slim@sha256:9f841bbe9e7d8e37ceb96ed907265a3a0df7f44e3737d0b100e7907a679acb36
# Single-stage: agent and verifier re-run cargo build after repair.
FROM public.ecr.aws/docker/library/rust:1.85-slim@sha256:9f841bbe9e7d8e37ceb96ed907265a3a0df7f44e3737d0b100e7907a679acb36

ENV DEBIAN_FRONTEND=noninteractive
ENV TERM=xterm
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8
ENV TMUX_TMPDIR=/var/tmp/tmux
ENV PATH="/usr/local/cargo/bin:/app/bin:/opt/verifier-venv/bin:${PATH}"

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    asciinema=2.2.0-1 \
    ca-certificates=20230311+deb12u1 \
    coreutils=9.1-1 \
    ncurses-term=6.4-4 \
    patch=2.7.6-7 \
    python3=3.11.2-1+b1 \
    python3-venv=3.11.2-1+b1 \
    tmux=3.3a-3 \
    && mkdir -p /var/tmp/tmux /app/bin /app/output /app/var/lane_cache \
    && chmod 1777 /var/tmp/tmux \
    && rm -rf /var/lib/apt/lists/*

COPY runtime/tmux.conf /etc/tmux.conf
COPY requirements.txt /tmp/requirements.txt
RUN python3 -m venv /opt/verifier-venv
RUN /opt/verifier-venv/bin/pip install --no-cache-dir --require-hashes -r /tmp/requirements.txt
RUN ln -sf /opt/verifier-venv/bin/pytest /usr/local/bin/pytest
RUN ln -sf /usr/local/cargo/bin/cargo /usr/local/bin/cargo

COPY Cargo.toml Cargo.lock /app/
COPY src /app/src
COPY data /app/data
COPY docs /app/docs
COPY schemas /app/schemas
COPY var /app/var

RUN cargo build --release --locked \
    && cp /app/target/release/m6_ctl /app/bin/m6_ctl \
    && ln -snf /app /app/environment

CMD ["/bin/bash"]
