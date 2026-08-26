FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac

ENV DEBIAN_FRONTEND=noninteractive
ENV TERM=xterm
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8
ENV TMUX_TMPDIR=/var/tmp/tmux

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    asciinema=2.2.0-1 \
    ca-certificates=20230311+deb12u1 \
    ncurses-term=6.4-4 \
    python3=3.11.2-1+b1 \
    python3-venv=3.11.2-1+b1 \
    tmux=3.3a-3 \
&& mkdir -p /var/tmp/tmux \
    && chmod 1777 /var/tmp/tmux \
    && rm -rf /var/lib/apt/lists/*

COPY runtime/tmux.conf /etc/tmux.conf

COPY go.mod /app/environment/
COPY cmd_h6 /app/environment/cmd_h6
COPY mod_h4 /app/environment/mod_h4
COPY mod_s7 /app/environment/mod_s7
COPY mod_b9 /app/environment/mod_b9
COPY mod_r2 /app/environment/mod_r2
COPY mod_q1 /app/environment/mod_q1
COPY mod_j3 /app/environment/mod_j3
COPY internal /app/environment/internal
COPY fixtures /app/environment/fixtures
COPY tooling /app/environment/tooling
COPY cfg /app/environment/cfg
COPY misc /app/environment/misc

RUN mkdir -p /app/output /app/var /app/tooling /app/environment/tools \
    && cd /app/environment \
    && chmod +x tooling/rebuild_h6.sh tooling/run_h6.sh tooling/wit_check.sh \
    && cp tooling/run_h6.sh /app/tooling/run_h6.sh \
    && chmod +x /app/tooling/run_h6.sh

ENV PATH="/app/environment/tools:/usr/local/go/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

RUN python3 -m venv /opt/verifier-venv \
    && /opt/verifier-venv/bin/pip install --no-cache-dir \
        pytest==8.4.1 \
        pytest-json-ctrf==0.3.5

# Verifier rebuild entry: /app/environment/tooling/rebuild_h6.sh
