FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac AS builder
WORKDIR /build
COPY app/go.mod ./
RUN go mod download
COPY app/ ./
RUN mkdir -p /build/bin && CGO_ENABLED=0 go build -o /build/bin/lng-boiloff-reconciler ./cmd/lng-boiloff-reconciler

FROM public.ecr.aws/docker/library/debian:bookworm-slim@sha256:4724b8cc51e33e398f0e2e15e18d5ec2851ff0c2280647e1310bc1642182655d
LABEL org.opencontainers.image.title="lng-tank-boiloff-reconciler"
LABEL org.opencontainers.image.licenses="MIT"
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
    asciinema \
    ca-certificates \
    passwd \
    python3 \
    python3-pip \
    python3-venv \
    strace \
    tmux \
    util-linux \
 && rm -rf /var/lib/apt/lists/* \
 && useradd --system --uid 10001 --home-dir /home/boiloff --create-home --shell /usr/sbin/nologin boiloff \
 && mkdir -p /opt/verifier-private /opt/verifier-venv \
 && chown root:root /opt/verifier-private /opt/verifier-venv \
 && chmod 700 /opt/verifier-private /opt/verifier-venv
COPY requirements.lock /tmp/requirements.lock
RUN python3 -m venv /opt/verifier-venv \
 && /opt/verifier-venv/bin/pip install --no-cache-dir --require-hashes -r /tmp/requirements.lock \
 && rm -f /tmp/requirements.lock \
 && chmod -R go-rwx /opt/verifier-venv
COPY --from=builder /usr/local/go /usr/local/go
WORKDIR /app
COPY app/ /app/
COPY --from=builder /build/bin/lng-boiloff-reconciler /app/bin/lng-boiloff-reconciler
RUN chmod +x /app/scripts/build.sh /app/bin/lng-boiloff-reconciler \
 && ln -sf /usr/local/go/bin/go /usr/local/bin/go \
 && ln -sf /usr/local/go/bin/gofmt /usr/local/bin/gofmt \
 && mkdir -p /app/bin /app/output /app/state \
 && chown boiloff:boiloff /app/output /app/state
ENV PATH="/usr/local/go/bin:/app/bin:${PATH}"
ENV CGO_ENABLED=0
ENV TZ=UTC
ENV BOILOFF_RUN_USER=boiloff
