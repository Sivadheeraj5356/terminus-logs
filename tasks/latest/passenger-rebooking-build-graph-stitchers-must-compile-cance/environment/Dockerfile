FROM --platform=linux/amd64 public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        asciinema \
        bash \
        ca-certificates \
        python3 \
        python3-pip \
        python3-venv \
        tmux \
        util-linux \
    && rm -rf /var/lib/apt/lists/*

# Keep image USER=root so Harbor/Daytona can create writable mounts.
# Agent interactive sessions drop to rebooker via this tmux wrapper.
# Strip CRLF at build time — a CR on the shebang makes exec of /usr/bin/tmux
# fail with exit 127 and can surface as EnvironmentStartTimeoutError.
RUN mv /usr/bin/tmux /usr/bin/tmux.real
COPY --chmod=0755 scripts/tmux-wrapper.sh /usr/bin/tmux
RUN sed -i 's/\r$//' /usr/bin/tmux

COPY requirements.lock /tmp/requirements.lock
RUN python3 -m venv /opt/verifier-venv \
    && /opt/verifier-venv/bin/pip install --no-cache-dir \
        --require-hashes --no-deps -r /tmp/requirements.lock \
    && rm -rf /root/.cache/pip /tmp/requirements.lock \
    && chown -R root:root /opt/verifier-venv \
    && chmod -R a+rX,go-w /opt/verifier-venv

# Small root-owned grading copies only — do not recursively rewrite /usr/local/go
# (that duplicates the toolchain layer and broke platform CodeBuild).
RUN mkdir -p /opt/verifier-image \
    && cp -a /usr/local/go/bin/go /opt/verifier-image/go \
    && cp -a /usr/sbin/runuser /opt/verifier-image/runuser \
    && chown root:root /opt/verifier-image/go /opt/verifier-image/runuser \
    && chmod 0555 /opt/verifier-image/go /opt/verifier-image/runuser

ENV CGO_ENABLED=0
ENV GOTOOLCHAIN=local
ENV GOPROXY=off
ENV GOFLAGS=-mod=mod
ENV GOCACHE=/tmp/gocache
ENV GOTMPDIR=/tmp/gotmp
ENV GOMODCACHE=/tmp/gomodcache
ENV GOROOT=/usr/local/go

WORKDIR /app

RUN groupadd --gid 1001 rebooker \
    && useradd --uid 1001 --gid rebooker --shell /bin/bash \
        --create-home --home-dir /home/rebooker rebooker

COPY --chown=1001:1001 go.mod ./
COPY --chown=1001:1001 cmd/ cmd/
COPY --chown=1001:1001 internal/ internal/
COPY --chown=1001:1001 docs/ docs/
COPY --chown=1001:1001 data/ data/
COPY --chmod=0755 --chown=1001:1001 scripts/build.sh scripts/build.sh

RUN mkdir -p /tmp/gocache /tmp/gotmp /tmp/gomodcache /app/output /app/state /app/bin \
    && sed -i 's/\r$//' /app/scripts/build.sh \
    && chown -R rebooker:rebooker /app /tmp/gocache /tmp/gotmp /tmp/gomodcache /home/rebooker \
    && chmod 1777 /tmp/gocache /tmp/gotmp /tmp/gomodcache

# Default user remains root (Harbor mount bootstrap). Agent tmux sessions run as rebooker.
ENV PATH="/usr/local/go/bin:/usr/bin:${PATH}"
