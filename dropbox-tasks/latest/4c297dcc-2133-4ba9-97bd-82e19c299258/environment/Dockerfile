FROM gcc:13-bookworm@sha256:930f2ebe239275fa67226654cb79273ea34eee672ae61c8a39f689c37fb7ac5c

ENV DEBIAN_FRONTEND=noninteractive
ENV TERM=xterm
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8
ENV TMUX_TMPDIR=/var/tmp/tmux
ENV TZ=UTC

RUN apt-get update && apt-get install -y --no-install-recommends asciinema=2.2.0-1 ca-certificates=20230311+deb12u1 ncurses-term=6.4-4 python3=3.11.2-1+b1 python3-venv=3.11.2-1+b1 tmux=3.3a-3 && rm -rf /var/lib/apt/lists/* && mkdir -p /var/tmp/tmux && chmod 1777 /var/tmp/tmux

RUN python3 -m venv /opt/verifier-venv \
    && /opt/verifier-venv/bin/pip install --no-cache-dir \
        pytest==8.4.1 \
        pytest-json-ctrf==0.3.5

WORKDIR /app

COPY runtime/tmux.conf /etc/tmux.conf
COPY Makefile /app/Makefile
COPY include /app/include
COPY mask /app/mask
COPY bound /app/bound
COPY lane /app/lane
COPY s6_host /app/s6_host
COPY t11_host /app/t11_host
COPY gate /app/gate
COPY load /app/load
COPY probe /app/probe
COPY snap /app/snap
COPY state /app/state
COPY lib /app/lib
COPY d8_cases /app/d8_cases
COPY work /app/work
COPY docs /app/docs
COPY tools /app/tools

RUN chmod +x /app/d8_cases/inspect/row_query.sh \
    && mkdir -p /app/output /app/var /app/build /app/environment \
    && for item in Makefile include mask bound lane s6_host t11_host gate load probe snap state lib d8_cases work docs tools; do \
         ln -sfn "/app/${item}" "/app/environment/${item}"; \
       done \
    && make -C /app/environment all -j2
