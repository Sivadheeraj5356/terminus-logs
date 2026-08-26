# Offline image (allow_internet=false): C toolchain via build-essential;
# final runtime uses canonical public.ecr.aws python:3.13-slim-bookworm.
FROM public.ecr.aws/docker/library/python:3.13-slim-bookworm@sha256:01f42367a0a94ad4bc17111776fd66e3500c1d87c15bbd6055b7371d39c124fb

LABEL org.opencontainers.image.title="pam-audit-replay"
LABEL org.opencontainers.image.created="1970-01-01T00:00:00Z"
LABEL org.opencontainers.image.version="1.0"
LABEL org.opencontainers.image.licenses="MIT"

# Session tooling + C build deps in one apt layer (allow_internet=false).
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        asciinema=2.2.0-1 \
        build-essential=12.9 \
        ca-certificates=20230311+deb12u1 \
        libevent-core-2.1-7=2.1.12-stable-8 \
        libutempter0=1.2.1-3 \
        tmux=3.3a-3 \
    && apt-mark manual \
        tmux asciinema libevent-core-2.1-7 libutempter0 \
    && rm -rf /var/lib/apt/lists/* \
    && install -d -m 1777 /tmp \
    && install -d -m 0777 /root /tmp/.config /tmp/.config/asciinema \
    && command -v tmux \
    && command -v asciinema \
    && tmux -V \
    && asciinema --version \
    && HOME=/tmp TMUX_TMPDIR=/tmp TERM=xterm-256color \
        tmux new-session -d -s _sess_a sleep 5 \
    && HOME=/tmp TMUX_TMPDIR=/tmp tmux kill-session -t _sess_a

WORKDIR /app

ENV HOME=/tmp
ENV TMUX_TMPDIR=/tmp
ENV TERM=xterm-256color
ENV XDG_CONFIG_HOME=/tmp/.config
ENV SOURCE_DATE_EPOCH=0
ENV PATH="/app/bin:/usr/local/bin:/usr/bin:/bin"

RUN ln -sf /usr/local/bin/python3.13 /usr/bin/python3 \
    && ln -sf /usr/local/bin/python3.13 /usr/bin/python

# Verifier-only: pytest + pytest-json-ctrf + asciinema (pinned); no runtime installs in tests/test.sh.
COPY verifier-requirements.txt /opt/verifier-requirements.txt
RUN python3 -m pip install --no-cache-dir --break-system-packages \
        -r /opt/verifier-requirements.txt

RUN rm -rf /root/.cache/pip \
    && python3 -m pytest --version \
    && command -v tmux \
    && command -v asciinema \
    && tmux -V \
    && asciinema --version \
    && HOME=/tmp TMUX_TMPDIR=/tmp TERM=xterm-256color \
        tmux new-session -d -s _sess_c sleep 5 \
    && HOME=/tmp TMUX_TMPDIR=/tmp tmux kill-session -t _sess_c

# Project sources (narrow COPY; build inputs only, excludes solution/ and tests/).
COPY Makefile /app/Makefile
COPY include /app/include
COPY cfg /app/cfg
COPY tape /app/tape
COPY fail /app/fail
COPY acct /app/acct
COPY bind /app/bind
COPY canon /app/canon
COPY lock /app/lock
COPY internal /app/internal
COPY audit /app/audit
COPY util /app/util
COPY decoy /app/decoy
COPY main.c /app/main.c
COPY --chmod=0755 scripts /app/scripts
COPY --chmod=0755 tools /app/tools
COPY config /app/config
COPY ctl /app/ctl
COPY rt /app/rt
COPY data /app/data
COPY var /app/var
COPY docs /app/docs
COPY schemas /app/schemas
COPY ops /app/ops
COPY dashboard /app/dashboard

# Warm build, drop object files in the same layer.
RUN install -d -m 0777 /app/output /app/bin /app/var/tally /app/ctl /app/rt \
    && chmod 0755 /app/scripts/*.sh /app/rt/export_env.sh /app/tools/auth_tape_replay \
    && bash /app/scripts/build.sh \
    && find /app -name '*.o' -delete \
    && command -v /app/bin/pam_audit \
    && command -v /app/scripts/stack_probe.sh \
    && command -v tmux \
    && command -v asciinema \
    && tmux -V \
    && asciinema --version \
    && HOME=/tmp TMUX_TMPDIR=/tmp TERM=xterm-256color \
        tmux new-session -d -s _sess_d sleep 5 \
    && HOME=/tmp TMUX_TMPDIR=/tmp tmux kill-session -t _sess_d

ENV PATH="/app/bin:${PATH}"

# Final gate: tmux/asciinema must survive the full image build.
RUN install -d -m 1777 /tmp \
    && install -d -m 0777 /tmp/.config /tmp/.config/asciinema \
    && command -v tmux \
    && command -v asciinema \
    && tmux -V \
    && asciinema --version \
    && HOME=/tmp TMUX_TMPDIR=/tmp TERM=xterm-256color \
        tmux kill-server 2>/dev/null || true \
    && tmux new-session -d -s _sess_e sleep 5 \
    && tmux has-session -t _sess_e \
    && HOME=/tmp TMUX_TMPDIR=/tmp tmux kill-session -t _sess_e

# Re-apply /tmp session prerequisites and verify tmux at container start (platforms may remount /tmp).
CMD ["bash", "-c", "chmod 1777 /tmp && install -d -m 0777 /tmp/.config/asciinema && export HOME=/tmp TMUX_TMPDIR=/tmp TERM=xterm-256color XDG_CONFIG_HOME=/tmp/.config && command -v tmux && command -v asciinema && tmux kill-server 2>/dev/null || true && tmux new-session -d -s _sess_boot sleep 1 && tmux has-session -t _sess_boot && tmux kill-session -t _sess_boot && exec sleep infinity"]
