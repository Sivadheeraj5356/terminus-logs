FROM --platform=linux/amd64 public.ecr.aws/docker/library/gcc:13-bookworm@sha256:930f2ebe239275fa67226654cb79273ea34eee672ae61c8a39f689c37fb7ac5c

WORKDIR /app

SHELL ["/bin/bash", "-c"]

ENV TMUX_TMPDIR=/tmp/.harbor-tmux \
    TERM=xterm-256color \
    SHELL=/bin/bash

RUN apt-get update && apt-get install -y --no-install-recommends \
    asciinema \
    bash \
    ca-certificates \
    cmake \
    libssl-dev \
    make \
    nlohmann-json3-dev \
    python3 \
    python3-pip \
    python3-venv \
    tmux \
    && mkdir -p /tmp/.harbor-tmux \
    && chmod 1777 /tmp/.harbor-tmux \
    && rm -rf /var/lib/apt/lists/* \
    && python3 -m venv /opt/verifier-venv

COPY requirements.txt /tmp/requirements.txt
RUN /opt/verifier-venv/bin/pip install --no-cache-dir --require-hashes -r /tmp/requirements.txt

COPY CMakeLists.txt /app/
COPY include /app/include
COPY src /app/src
COPY docs /app/docs
COPY fixtures /app/fixtures
COPY scripts /app/scripts
COPY tools /app/tools
COPY README.md /app/README.md

RUN chmod +x /app/tools/*.sh /app/scripts/*.sh \
    && bash /app/tools/build.sh \
    && mkdir -p /app/output /app/var /app/state \
    && ln -sfn /app /app/environment

ENV PATH="/opt/verifier-venv/bin:/app/bin:${PATH}"
