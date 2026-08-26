FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac
ENV PATH="/usr/local/go/bin:${PATH}"
RUN ln -sf /usr/local/go/bin/go /usr/local/bin/go && ln -sf /usr/local/go/bin/gofmt /usr/local/bin/gofmt && ln -sf /usr/local/go/bin/go /usr/bin/go

# Fully offline OS-package install: the runtime deps (tmux, asciinema, python3
# + venv + pip) are vendored as .deb files under vendor/debs and installed with
# dpkg so `docker build` needs NO network (allow_internet=false). The .deb set is
# the exact dependency closure resolved against this base image.
COPY vendor/debs /tmp/debs
RUN dpkg -i /tmp/debs/*.deb \
    && rm -rf /tmp/debs /var/lib/apt/lists/*

COPY requirements.lock /tmp/requirements.lock
COPY vendor/wheels /tmp/wheels
RUN python3 -m venv /opt/verifier \
    && /opt/verifier/bin/pip install --no-cache-dir --no-index --find-links=/tmp/wheels --require-hashes -r /tmp/requirements.lock \
    && rm /tmp/requirements.lock

ENV GOFLAGS=-mod=mod
ENV GOTOOLCHAIN=local
ENV GOPROXY=off
ENV GOSUMDB=off

WORKDIR /app

COPY go.mod /app/go.mod
COPY cmd /app/cmd
COPY internal /app/internal
COPY docs /app/docs
COPY data /app/data

# Warm the Go build cache and confirm the scaffold compiles, but do NOT leave a
# candidate binary at /app/bin/spoold: the agent must build it during the agent
# phase and the verifier recompiles it from /app/internal/sp/sp.go, so the build
# check reflects the current source rather than a pre-baked executable.
RUN cd /app && go build -o /tmp/spoold-warm ./cmd/spoold && rm -f /tmp/spoold-warm
