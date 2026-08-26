FROM gcc:13-bookworm@sha256:930f2ebe239275fa67226654cb79273ea34eee672ae61c8a39f689c37fb7ac5c

ENV DEBIAN_FRONTEND=noninteractive
ENV TERM=xterm
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8
ENV TMUX_TMPDIR=/var/tmp/tmux
ENV PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends python3=3.11.2-1+b1 \
    asciinema=2.2.0-1 \
    ca-certificates=20230311+deb12u1 \
    libssl-dev=3.0.18-1~deb12u2 \
    openssl=3.0.18-1~deb12u2 \
    make=4.3-4.1 \
    ncurses-term=6.4-4 \
    python3-venv=3.11.2-1+b1 \
    tmux=3.3a-3 \
    && mkdir -p /var/tmp/tmux \
    && chmod 1777 /var/tmp/tmux \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv /opt/verifier-venv \
    && /opt/verifier-venv/bin/pip install --no-cache-dir \
        pytest==8.4.1 \
        pytest-json-ctrf==0.3.5

COPY runtime/tmux.conf /etc/tmux.conf
COPY Makefile /app/environment/Makefile
COPY lib /app/environment/lib
COPY sig /app/environment/sig
COPY kel /app/environment/kel
COPY tools /app/environment/tools
COPY ci /app/environment/ci
COPY data /app/environment/data
COPY docs /app/environment/docs

RUN mkdir -p /app/environment/bin /app/output \
    && chmod +x /app/environment/ci/rebuild.sh \
    && cd /app/environment && make -j"$(nproc)"
