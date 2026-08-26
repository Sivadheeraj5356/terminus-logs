FROM rust:1.85-slim@sha256:9f841bbe9e7d8e37ceb96ed907265a3a0df7f44e3737d0b100e7907a679acb36

ENV DEBIAN_FRONTEND=noninteractive
ENV TERM=xterm
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8
ENV TMUX_TMPDIR=/var/tmp/tmux

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3=3.11.2-1+b1 \
    python3-venv=3.11.2-1+b1 \
    asciinema=2.2.0-1 \
    ca-certificates=20230311+deb12u1 \
    ncurses-term=6.4-4 \
    openssl=3.0.17-1~deb12u2 \
    tmux=3.3a-3 \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /var/tmp/tmux \
    && chmod 1777 /var/tmp/tmux

COPY runtime/tmux.conf /etc/tmux.conf
COPY runtime/tmux-wrapper.sh /tmp/tmux-wrapper.sh
COPY runtime/run_lab.sh /tmp/run_lab.sh
RUN sed -i 's/\r$//' /etc/tmux.conf /tmp/tmux-wrapper.sh /tmp/run_lab.sh \
    && mv /usr/bin/tmux /usr/bin/tmux.real \
    && mv /tmp/tmux-wrapper.sh /usr/bin/tmux \
    && chmod 755 /usr/bin/tmux \
    && tmux start-server \
    && (tmux kill-server 2>/dev/null || true) \
    && rm -rf /var/tmp/tmux/*

COPY Cargo.toml Cargo.lock /app/environment/
COPY lib.rs main.rs /app/environment/
COPY ingest /app/environment/ingest
COPY seg /app/environment/seg
COPY k2 /app/environment/k2
COPY m4 /app/environment/m4
COPY p9 /app/environment/p9
COPY r3 /app/environment/r3
COPY s6 /app/environment/s6
COPY w8 /app/environment/w8
COPY h9 /app/environment/h9
COPY n2 /app/environment/n2
COPY n7 /app/environment/n7
COPY shared /app/environment/shared
COPY vendor_stub /app/environment/vendor_stub
COPY data /app/environment/data
COPY docs /app/environment/docs
COPY scripts /app/environment/scripts

RUN mkdir -p /app/bin /app/output /app/var \
    && sed -i 's/\r$//' /app/environment/scripts/rebuild_pathlab.sh \
    && chmod +x /app/environment/scripts/rebuild_pathlab.sh \
    && /app/environment/scripts/rebuild_pathlab.sh \
    && mv /tmp/run_lab.sh /app/bin/run_lab \
    && chmod 755 /app/bin/run_lab

RUN python3 -m venv /opt/verifier-venv \
    && /opt/verifier-venv/bin/pip install --no-cache-dir \
        pytest==8.4.1 \
        pytest-json-ctrf==0.3.5

CMD ["sleep", "infinity"]
