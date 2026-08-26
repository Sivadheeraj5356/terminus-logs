# Canonical Debian bookworm-slim (docs/CANONICAL_BASE_IMAGES.md). build-essential/gcc below
# supply the C toolchain; canonical Python t-bench images omit those compile deps.
# Apt version pins match this digest; refresh pins if the base digest changes.
FROM public.ecr.aws/docker/library/debian:bookworm-slim@sha256:4724b8cc51e33e398f0e2e15e18d5ec2851ff0c2280647e1310bc1642182655d

ENV DEBIAN_FRONTEND=noninteractive
ENV TERM=xterm
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8
ENV TMUX_TMPDIR=/var/tmp/tmux
ENV SHELL=/bin/bash

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends build-essential=12.9 gcc=4:12.2.0-3 make=4.3-4.1 \
    asciinema=2.2.0-1 \
    ca-certificates=20230311+deb12u1 \
    coreutils=9.1-1 \
    ncurses-term=6.4-4 \
    python3=3.11.2-1+b1 \
    python3-venv=3.11.2-1+b1 \
    tmux=3.3a-3 \
    && mkdir -p /var/tmp/tmux \
    && chmod 1777 /var/tmp/tmux \
    && rm -rf /var/lib/apt/lists/* \
    && command -v tmux >/dev/null \
    && command -v asciinema >/dev/null

COPY runtime/tmux.conf /etc/tmux.conf
COPY requirements.lock /tmp/requirements.txt

RUN python3 -m venv /opt/verifier-venv \
    && /opt/verifier-venv/bin/pip install --no-cache-dir --require-hashes --no-deps -r /tmp/requirements.txt

COPY Makefile /app/environment/Makefile
COPY lib /app/environment/lib
COPY d0 /app/environment/d0
COPY u4_pin /app/environment/u4_pin
COPY m1_key /app/environment/m1_key
COPY p5_hand /app/environment/p5_hand
COPY trace /app/environment/trace
COPY q3_probe /app/environment/q3_probe
COPY tools /app/environment/tools
COPY fixtures /app/environment/fixtures
COPY cfg /app/environment/cfg
COPY misc /app/environment/misc

RUN make -C /app/environment all \
    && mkdir -p /app/output /app/work/policy \
    && chmod +x /app/environment/tools/j4_round /app/environment/tools/p7_emit \
    && chmod +x /app/environment/q3_probe/*.sh

ENV PATH="/app/environment/tools:/app/environment/d0:/app/environment/trace:/app/environment/q3_probe:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
