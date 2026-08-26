FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac

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
    && pip install --break-system-packages pytest==8.4.1 pytest-json-ctrf==0.3.5 \
    && ln -sf /usr/local/go/bin/go /usr/local/bin/go \
    && ln -sf /usr/local/go/bin/gofmt /usr/local/bin/gofmt

ENV GOCACHE=/tmp/go-cache GOPATH=/tmp/go-path
RUN mkdir -p /tmp/go-cache /tmp/go-path && chmod -R 0777 /tmp/go-cache /tmp/go-path

WORKDIR /app
COPY repo/ /app/

RUN git config --system --add safe.directory /app \
    && git init -q \
    && git config user.email task@example.com \
    && git config user.name task \
    && git add -A \
    && git commit -q -m "initial task state"
