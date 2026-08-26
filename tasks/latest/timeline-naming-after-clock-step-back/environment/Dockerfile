# Canonical Debian bookworm-slim runtime (docs/CANONICAL_BASE_IMAGES.md).
FROM debian:bookworm-slim@sha256:4724b8cc51e33e398f0e2e15e18d5ec2851ff0c2280647e1310bc1642182655d

ENV DEBIAN_FRONTEND=noninteractive
ENV TERM=xterm
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8
ENV TMUX_TMPDIR=/var/tmp/tmux

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    asciinema=2.2.0-1 \
    ca-certificates=20230311+deb12u1 \
    jq=1.6-2.1+deb12u2 \
    libjq1=1.6-2.1+deb12u2 \
    ncurses-term=6.4-4 \
    openssl=3.0.20-1~deb12u2 \
    python3=3.11.2-1+b1 \
    python3-venv=3.11.2-1+b1 \
    tmux=3.3a-3 \
    && mkdir -p /var/tmp/tmux /app/output /app/svc-state/replay_material /app/svc-state/checkpoint /app/state/handoff \
    && chmod 1777 /var/tmp/tmux \
    && rm -rf /var/lib/apt/lists/*

COPY runtime/tmux.conf /etc/tmux.conf
COPY runtime/verifier-requirements.txt /opt/verifier-requirements.txt

RUN python3 -m venv /opt/verifier-venv \
    && /opt/verifier-venv/bin/pip install --no-cache-dir --require-hashes \
        -r /opt/verifier-requirements.txt

COPY svc-state-seed/checkpoint/epoch.json /app/svc-state/checkpoint/epoch.json
COPY svc-state-seed/replay_material/ /app/svc-state/replay_material/
COPY . /app/environment

RUN chmod +x /app/environment/scripts/*.sh /app/environment/u0_a/*.sh \
    /app/environment/u1_b/*.sh /app/environment/u2_c/*.sh /app/environment/u3_d/*.sh \
    /app/environment/hrun/*.sh /app/environment/vstore/*.sh /app/environment/snaplab/*.sh \
    && mkdir -p /app/docs \
    && ln -sf /app/environment/docs/resume_contract.md /app/docs/resume_contract.md \
    && ln -sf /app/environment/docs/precedence_notes.md /app/docs/precedence_notes.md

CMD ["/bin/bash"]
