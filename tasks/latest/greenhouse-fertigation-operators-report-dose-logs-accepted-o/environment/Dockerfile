FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac AS builder

WORKDIR /build
COPY app/go.mod ./
RUN go mod download && go mod tidy
COPY app/ ./
RUN go mod tidy && go mod vendor \
    && CGO_ENABLED=1 go build -mod=vendor -o /build/out/fert-ingest ./cmd/fert-ingest \
    && CGO_ENABLED=1 go build -mod=vendor -o /build/out/fert-export ./cmd/fert-export

FROM public.ecr.aws/docker/library/debian:bookworm-slim@sha256:4724b8cc51e33e398f0e2e15e18d5ec2851ff0c2280647e1310bc1642182655d

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        asciinema \
        build-essential \
        ca-certificates \
        python3 \
        python3-pip \
        python3-venv \
        sqlite3 \
        tmux \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-verifier.txt /tmp/requirements-verifier.txt
RUN python3 -m venv /opt/verifier-venv \
    && /opt/verifier-venv/bin/pip install --no-cache-dir -r /tmp/requirements-verifier.txt \
    && rm -f /tmp/requirements-verifier.txt

COPY --from=builder /usr/local/go /usr/local/go
ENV PATH="/usr/local/go/bin:/app/bin:${PATH}"
ENV CGO_ENABLED=1

WORKDIR /app
COPY app/ /app/
COPY --from=builder /build/vendor /app/vendor
COPY --from=builder /build/go.sum /app/go.sum
COPY --from=builder /build/out/fert-ingest /app/bin/fert-ingest
COPY --from=builder /build/out/fert-export /app/bin/fert-export

RUN chmod +x /app/scripts/build.sh \
    && mkdir -p /app/data /app/output /app/bin

CMD ["sleep", "infinity"]
