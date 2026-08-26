# Digest-pinned Ubuntu 24.04 runtime base.
# Headless agent harnesses (e.g. terminus-2/tmux) expect tmux, TERM, and a socket dir.
FROM public.ecr.aws/docker/library/ubuntu:24.04@sha256:0d39fcc8335d6d74d5502f6df2d30119ff4790ebbb60b364818d5112d9e3e932

ENV DEBIAN_FRONTEND=noninteractive
ENV TERM=xterm
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8
ENV TMUX_TMPDIR=/var/tmp/tmux

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends golang-go=2:1.22~2build1 python3=3.12.3-0ubuntu2.1 \
    python3-venv=3.12.3-0ubuntu2.1 \
    python3-pip=24.0+dfsg-1ubuntu1.3 \
    ca-certificates=20240203 \
    openssl=3.0.13-0ubuntu3.11 \
    ncurses-term=6.4+20240113-1ubuntu2 \
    tmux=3.4-1ubuntu0.1 \
    asciinema=2.4.0-1 \
&& mkdir -p /var/tmp/tmux \
    && chmod 1777 /var/tmp/tmux \
    && rm -rf /var/lib/apt/lists/*

COPY runtime/tmux.conf /etc/tmux.conf
COPY runtime/install_verifier_deps.sh /usr/local/bin/install_verifier_deps.sh
COPY requirements.lock /tmp/requirements.lock
RUN python3 -m venv /opt/verifier-venv \
    && chmod +x /usr/local/bin/install_verifier_deps.sh \
    && /usr/local/bin/install_verifier_deps.sh /opt/verifier-venv/bin/pip /tmp/requirements.lock
RUN /opt/verifier-venv/bin/pytest --version

ENV PATH="/opt/verifier-venv/bin:/usr/bin:${PATH}"
ENV GOCACHE=/tmp/gocache
ENV GOMODCACHE=/tmp/gomodcache

COPY . /app/environment

RUN mkdir -p /app/bin /app/output /app/state \
    && printf '%s\n' '{"fixture_label":"pack_m3","reader_epoch":"stale99","observed_bytes":500}' > /app/state/resume.offset
