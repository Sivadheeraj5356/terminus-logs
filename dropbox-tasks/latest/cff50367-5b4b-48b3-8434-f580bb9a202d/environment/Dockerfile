FROM debian:bookworm-slim@sha256:4724b8cc51e33e398f0e2e15e18d5ec2851ff0c2280647e1310bc1642182655d

ENV DEBIAN_FRONTEND=noninteractive
ENV TERM=xterm
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8
ENV TMUX_TMPDIR=/var/tmp/tmux

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends golang-go=2:1.19~1 \
    asciinema=2.2.0-1 \
    ca-certificates=20230311+deb12u1 \
    ncurses-term=6.4-4 \
    python3=3.11.2-1+b1 \
    python3-venv=3.11.2-1+b1 \
    tmux=3.3a-3 \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /var/tmp/tmux \
    && chmod 1777 /var/tmp/tmux

COPY verifier-requirements.txt /tmp/verifier-requirements.txt
RUN python3 -m venv /opt/verifier-venv \
    && /opt/verifier-venv/bin/pip install --no-cache-dir --require-hashes -r /tmp/verifier-requirements.txt

COPY runtime/tmux.conf /etc/tmux.conf
COPY go.mod /app/environment/go.mod
COPY model/ /app/environment/model/
COPY feeder/ /app/environment/feeder/
COPY vault/ /app/environment/vault/
COPY quorum/ /app/environment/quorum/
COPY lapse/ /app/environment/lapse/
COPY weave/ /app/environment/weave/
COPY notary/ /app/environment/notary/
COPY extent/ /app/environment/extent/
COPY dossier/ /app/environment/dossier/
COPY cli/ /app/environment/cli/
COPY cmd/ /app/environment/cmd/
COPY realms/ /app/environment/realms/
COPY manifest/ /app/environment/manifest/
COPY runtime/ /app/environment/runtime/
COPY fixtures/ /app/environment/fixtures/
COPY tools/ /app/environment/tools/
COPY docs/ /app/environment/docs/

# Agent and verifier both rebuild mux after source fixes; keep the Go toolchain
# in the runtime image (multi-stage carve-out for rebuild-at-runtime tasks).
RUN mkdir -p /app/bin /app/output \
    && cd /app/environment \
    && go build -o /app/bin/mux ./cmd/mux
