FROM public.ecr.aws/docker/library/debian:bookworm-slim@sha256:4724b8cc51e33e398f0e2e15e18d5ec2851ff0c2280647e1310bc1642182655d
# Canonical Debian bookworm-slim digest from docs/CANONICAL_BASE_IMAGES.md.

ENV DEBIAN_FRONTEND=noninteractive
ENV TERM=xterm
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8
ENV TMUX_TMPDIR=/var/tmp/tmux
ENV PATH=/usr/lib/go-1.19/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    asciinema=2.2.0-1 \
    ca-certificates=20230311+deb12u1 \
    golang-go=2:1.19~1 \
    ncurses-term=6.4-4 \
    python3=3.11.2-1+b1 \
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
COPY etc/ /app/environment/etc/
COPY go.mod /app/environment/go.mod
COPY model/ /app/environment/model/
COPY app/ /app/environment/app/
COPY cmd/ /app/environment/cmd/
COPY profiles/ /app/environment/profiles/
COPY compile/ /app/environment/compile/
COPY load/ /app/environment/load/
COPY enforce/ /app/environment/enforce/
COPY emit/ /app/environment/emit/
COPY docs/ /app/environment/docs/
COPY conf/ /app/environment/conf/
COPY store/ /app/environment/store/
COPY fixtures/ /app/environment/fixtures/
COPY runtime/layout.json /app/environment/runtime/layout.json

RUN mkdir -p /app/bin /app/state /app/output \
    && cd /app/environment \
    && go build -o /app/bin/arctl ./cmd/arctl
