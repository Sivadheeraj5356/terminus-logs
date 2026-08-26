# syntax=docker/dockerfile:1

FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac AS inspect-builder
WORKDIR /build
COPY app/go.mod app/go.sum ./
COPY app/cmd/modpolicy-inspect ./cmd/modpolicy-inspect
COPY app/internal ./internal
RUN go build -o /out/modpolicy-inspect ./cmd/modpolicy-inspect

FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac
WORKDIR /app

# Pinned to Candidate versions from golang:1.24-bookworm (bookworm):
#   tmux=3.3a-3 asciinema=2.2.0-1 ca-certificates=20230311+deb12u1
#   python3=3.11.2-1+b1 python3-pip=23.0.1+dfsg-1 sqlite3=3.40.1-2+deb12u2
RUN apt-get update && apt-get install -y --no-install-recommends \
    tmux=3.3a-3 \
    asciinema=2.2.0-1 \
    ca-certificates=20230311+deb12u1 \
    python3=3.11.2-1+b1 \
    python3-pip=23.0.1+dfsg-1 \
    sqlite3=3.40.1-2+deb12u2 \
    && rm -rf /var/lib/apt/lists/* \
    && ln -sf python3 /usr/bin/python \
    && ln -sf /usr/local/go/bin/go /usr/local/bin/go \
    && ln -sf /usr/local/go/bin/gofmt /usr/local/bin/gofmt

RUN python3 -m pip install --no-cache-dir --break-system-packages \
    pytest==8.4.1 \
    pytest-json-ctrf==0.3.5 \
    jsonschema==4.23.0

COPY app /app
RUN mkdir -p /app/bin
COPY --from=inspect-builder /out/modpolicy-inspect /app/bin/modpolicy-inspect

ENV HOME=/root \
    MODPOLICY_OFFLINE=1 \
    GOPROXY=off \
    GOSUMDB=off \
    PATH=/usr/local/go/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

RUN mkdir -p /app/var/policy-index /output /logs/verifier /logs/agent \
    && chmod -R a-w /app/var/module-mirror /app/fixtures /app/schemas /app/docs \
    && chmod +x /app/scripts/*.sh /app/bin/modpolicy-inspect \
    && chmod 0755 /app/scripts/offline-modpolicy.sh

CMD ["sleep", "infinity"]
