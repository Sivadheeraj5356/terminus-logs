FROM public.ecr.aws/docker/library/gcc:13-bookworm@sha256:930f2ebe239275fa67226654cb79273ea34eee672ae61c8a39f689c37fb7ac5c

RUN apt-get update && apt-get install -y --no-install-recommends \
    tmux asciinema bash util-linux git ripgrep sed coreutils patch \
    python3 python3-pip python3-venv \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir --break-system-packages \
    pytest==8.3.5 pytest-json-ctrf==0.5.0

WORKDIR /app

COPY repo/ /app/

RUN git init -q \
    && git config user.email task@example.com \
    && git config user.name task \
    && git add -A \
    && git commit -q -m "initial task state"
