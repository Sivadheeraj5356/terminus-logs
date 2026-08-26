# Canonical digest-pinned Go image; verifier dependencies are installed during the image build and task execution stays offline.
FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac

WORKDIR /workspace
ENV TERM=xterm-256color
ENV TMUX_TMPDIR=/workspace/.tmux
RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-pytest tmux asciinema iproute2 ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && ln -sf /usr/local/go/bin/go /usr/local/bin/go \
    && ln -sf /usr/local/go/bin/gofmt /usr/local/bin/gofmt \
    && mkdir -p /workspace/.tmux \
    && chmod 1777 /workspace/.tmux \
    && chmod 1777 /tmp \
    && command -v go \
    && command -v gofmt \
    && command -v python3 \
    && command -v tmux \
    && command -v asciinema \
    && command -v ss

COPY go.mod ./go.mod
COPY cmd/ ./cmd/
COPY internal/ ./internal/
COPY docs/ ./docs/
COPY data/ ./data/
COPY notes/ ./notes/
COPY examples/ ./examples/
