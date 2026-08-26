FROM public.ecr.aws/docker/library/gcc:13-bookworm@sha256:930f2ebe239275fa67226654cb79273ea34eee672ae61c8a39f689c37fb7ac5c

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        bash \
        tmux \
        asciinema \
        util-linux \
        git \
        ripgrep \
        patch \
        ca-certificates \
        python3 \
        python3-pip \
    && rm -rf /var/lib/apt/lists/*

# Verifier-only dependencies, pinned and hash-locked.
COPY requirements.lock /tmp/requirements.lock
RUN pip install --no-cache-dir --break-system-packages --require-hashes -r /tmp/requirements.lock \
    && rm -f /tmp/requirements.lock

WORKDIR /app
COPY repo/ /app/

# Warm the build cache so the agent's post-edit rebuilds stay quick.
RUN g++ -O2 -std=c++17 /app/main.cpp -o /tmp/rpresolve && rm -f /tmp/rpresolve

RUN git init -q \
    && git config user.email task@example.com \
    && git config user.name task \
    && git add -A \
    && git commit -q -m "initial task state"
