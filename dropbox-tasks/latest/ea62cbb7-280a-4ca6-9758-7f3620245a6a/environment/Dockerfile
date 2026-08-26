FROM public.ecr.aws/docker/library/node:22-bookworm-slim@sha256:f3a68cf41a855d227d1b0ab832bed9749469ef38cf4f58182fb8c893bc462383

COPY wheels/ /opt/python-wheels/
COPY requirements.lock /opt/python-wheels/requirements.lock
RUN apt-get update && apt-get install -y --no-install-recommends \
        asciinema \
        bash \
        ca-certificates \
        coreutils \
        git \
        patch \
        python3 \
        python-is-python3 \
        python3-pip \
        ripgrep \
        sed \
        tmux \
        util-linux \
    && rm -rf /var/lib/apt/lists/* \
    && python3 -m pip install --break-system-packages --no-index \
        --find-links /opt/python-wheels \
        --require-hashes \
        --no-deps \
        -r /opt/python-wheels/requirements.lock

WORKDIR /app
COPY repo/ /app/
RUN chmod +x /app/bin/windowjudge.js /app/scripts/replay.sh \
    && node --check /app/bin/windowjudge.js \
    && node --check /app/lib/judge.js \
    && git init -q \
    && git config user.email task@example.com \
    && git config user.name task \
    && git add -A \
    && git commit -q -m "initial task state"
