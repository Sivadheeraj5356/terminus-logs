FROM gcc:13-bookworm@sha256:930f2ebe239275fa67226654cb79273ea34eee672ae61c8a39f689c37fb7ac5c

ENV DEBIAN_FRONTEND=noninteractive
ENV TERM=xterm
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8
ENV TMUX_TMPDIR=/var/tmp/tmux
ENV PATH=/opt/verifier/bin:${PATH}

RUN apt-get update && apt-get install -y --no-install-recommends \
    asciinema=2.2.0-1 \
    ca-certificates=20230311+deb12u1 \
    make=4.3-4.1 \
    ncurses-term=6.4-4 \
    python3=3.11.2-1+b1 \
    python3-venv=3.11.2-1+b1 \
    tmux=3.3a-3 \
  && rm -rf /var/lib/apt/lists/* \
  && mkdir -p /var/tmp/tmux \
  && chmod 1777 /var/tmp/tmux

RUN python3 -m venv /opt/verifier \
  && /opt/verifier/bin/pip install --no-cache-dir \
    pytest==8.4.1 \
    pytest-json-ctrf==0.3.5

WORKDIR /app

COPY runtime/tmux.conf /etc/tmux.conf
COPY Makefile /app/environment/Makefile
COPY include /app/environment/include
COPY l4 /app/environment/l4
COPY stamp /app/environment/stamp
COPY wait /app/environment/wait
COPY m7 /app/environment/m7
COPY persist /app/environment/persist
COPY n8_host /app/environment/n8_host
COPY harness /app/environment/harness
COPY tools /app/environment/tools
COPY docs /app/environment/docs
COPY n8_replays /app/environment/n8_replays

RUN mkdir -p /app/output /app/state /app/environment/build/bin \
  && chmod 0755 /app/environment/tools/n2_driver /app/environment/tools/w8_emit \
  && ln -snf /app/environment/docs /app/docs \
  && ln -snf /app/environment/tools /app/tools \
  && make -C /app/environment -j2

CMD ["sleep", "infinity"]
