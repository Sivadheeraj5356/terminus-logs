FROM public.ecr.aws/docker/library/gcc:13-bookworm@sha256:930f2ebe239275fa67226654cb79273ea34eee672ae61c8a39f689c37fb7ac5c

RUN apt-get update && apt-get install -y --no-install-recommends \
        asciinema \
        bash \
        ca-certificates \
        coreutils \
        git \
        patch \
        python3 \
        python3-pip \
        ripgrep \
        sed \
        tmux \
        util-linux \
    && pip3 install --break-system-packages --no-cache-dir \
        pytest==8.3.4 pytest-json-ctrf==0.3.5 \
    && rm -rf /var/lib/apt/lists/* \
    && command -v patch \
    && command -v python3 \
    && bash -lc 'command -v gcc make python3 patch' \
    && python3 -m pytest --version

WORKDIR /app
COPY repo/ /app/

RUN git init -q \
    && git config user.email task@example.com \
    && git config user.name task \
    && git add -A \
    && git commit -q -m "initial task state"
