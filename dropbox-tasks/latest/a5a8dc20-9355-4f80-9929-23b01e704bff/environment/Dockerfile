# Task revision v10.
# Canonical, sanctioned Go base (digest-pinned).
FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac

# The CUE module declares `go 1.25.0`, newer than the base's 1.24. Install that
# toolchain at build time (network is available during build) and pin it; the
# runtime build then reuses it fully offline.
ENV GOTOOLCHAIN=go1.25.0

# Agent runtime (tmux + asciinema) and a pinned pytest verifier toolchain.
RUN apt-get update && apt-get install -y --no-install-recommends \
        tmux asciinema python3 python3-venv ca-certificates \
    && rm -rf /var/lib/apt/lists/*
RUN python3 -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir pytest==8.4.1 pytest-json-ctrf==0.3.5
ENV PATH=/opt/venv/bin:$PATH

# The CUE engine source. The agent edits the sources under /app (notably the
# evaluator in internal/core/adt); all Go dependencies are vendored under
# /app/vendor. Runtime builds are fully offline.
WORKDIR /app
COPY app/ /app/

# Warm the toolchain download + the vendored build so the verifier's post-edit
# rebuild is fast and offline. Two `./...` builds (never an explicit main-package
# build, whose `cue` binary would collide with the repo's `cue/` directory): the
# first downloads the go1.25.0 toolchain (GOPROXY at default) and warms the
# vendored build; the second confirms the fully-offline build the verifier uses.
RUN GOFLAGS=-mod=vendor go build ./... \
    && GOFLAGS=-mod=vendor GOPROXY=off go build ./...
