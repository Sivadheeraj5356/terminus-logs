FROM public.ecr.aws/docker/library/gcc:13-bookworm@sha256:930f2ebe239275fa67226654cb79273ea34eee672ae61c8a39f689c37fb7ac5c

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tmux \
        asciinema \
        bash \
        git \
        patch \
        make \
        ripgrep \
        util-linux \
        ca-certificates \
        python3 \
        python3-pip \
        python3-venv \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --system --gid 10001 arcguard \
    && useradd --system --uid 10001 --gid arcguard --no-create-home --shell /usr/sbin/nologin arcguard

COPY requirements.lock /opt/requirements.lock
RUN python3 -m venv /opt/verifier-venv \
    && /opt/verifier-venv/bin/pip install --no-cache-dir --only-binary=:all: --require-hashes --no-deps -r /opt/requirements.lock
ENV VERIFIER_PYTHON=/opt/verifier-venv/bin/python
RUN ln -sf /opt/verifier-venv/bin/python /usr/local/bin/python3

WORKDIR /app
COPY repo/ /app/
RUN make arcguard && rm -f /app/arcguard
RUN git init -q \
    && git config user.email task@example.com \
    && git config user.name task \
    && git add -A \
    && git commit -q -m "initial task state"
