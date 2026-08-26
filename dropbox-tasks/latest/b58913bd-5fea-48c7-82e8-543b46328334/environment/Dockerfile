FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        asciinema \
        bash \
        ca-certificates \
        git \
        patch \
        python3 \
        python3-pip \
        ripgrep \
        tmux \
        util-linux \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.lock /tmp/requirements.lock
RUN pip3 install --break-system-packages --require-hashes --no-deps -r /tmp/requirements.lock \
    && rm /tmp/requirements.lock

# Put the Go toolchain on the default PATH so it is found in a login shell, and
# pre-create a shared build cache any user can write to. VCS stamping is off
# because the repo under /app may be owned by a different user than the builder.
RUN ln -sf /usr/local/go/bin/go /usr/local/bin/go \
    && ln -sf /usr/local/go/bin/gofmt /usr/local/bin/gofmt \
    && mkdir -m 777 -p /tmp/gocache /tmp/gopath
ENV GOCACHE=/tmp/gocache \
    GOPATH=/tmp/gopath \
    GOFLAGS=-buildvcs=false

WORKDIR /app
COPY --chown=1000:1000 --chmod=0777 repo/ /app/
# WORKDIR pre-created /app as root; hand the directory itself to the same
# owner as its contents (single directory, nothing recursive).
RUN chown 1000:1000 /app && chmod 777 /app

USER 1000:1000
RUN export HOME=/tmp && umask 000 \
    && git init -q \
    && git config user.email dev@example.com \
    && git config user.name dev \
    && git add -A \
    && git commit -q -m "initial import"
USER root
RUN git config --system --add safe.directory /app
