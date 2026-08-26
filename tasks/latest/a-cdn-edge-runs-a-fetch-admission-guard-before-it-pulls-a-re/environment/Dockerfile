FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac

ENV DEBIAN_FRONTEND=noninteractive
ENV GOTOOLCHAIN=auto
COPY requirements.lock /tmp/requirements.lock
RUN apt-get update && apt-get install -y --no-install-recommends \
        tmux \
        asciinema \
        bash \
        git \
        ripgrep \
        patch \
        util-linux \
        python3 \
        python3-pip \
    && python3 -m pip install --no-cache-dir --break-system-packages --require-hashes -r /tmp/requirements.lock \
    && ln -sf /usr/local/go/bin/go /usr/local/bin/go \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY repo/ /app/

# Warm-check the stub compiles so editing starts from a known-good state
# (no artifact is left behind; the graded binary is built separately).
RUN go build -o /dev/null .

# Make /app a git repo so git apply / git diff work in place.
RUN git init -q \
    && git config user.email task@example.com \
    && git config user.name task \
    && git add -A \
    && git commit -q -m "initial task state"
