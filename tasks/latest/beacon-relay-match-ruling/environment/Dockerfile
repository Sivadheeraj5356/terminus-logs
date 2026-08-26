# Sanctioned canonical Go runtime/build image; the task must compile a native Go ELF offline.
FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac

LABEL org.opencontainers.image.title="beacon-relay-adjudicator" \
      org.opencontainers.image.description="Offline Beacon Relay match environment" \
      org.opencontainers.image.base.name="public.ecr.aws/docker/library/golang:1.24-bookworm" \
      org.opencontainers.image.base.digest="sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac"

ENV PATH="/usr/local/go/bin:/go/bin:${PATH}" \
    GOTOOLCHAIN=local \
    GOPROXY=off \
    GOFLAGS=-mod=mod \
    CGO_ENABLED=0

RUN test -x /usr/local/go/bin/go \
    && test -x /usr/local/go/bin/gofmt \
    && ln -sf /usr/local/go/bin/go /usr/bin/go \
    && ln -sf /usr/local/go/bin/gofmt /usr/bin/gofmt \
    && go version

RUN apt-get update \
    && apt-get install -y --no-install-recommends tmux asciinema python3 python3-venv \
    && rm -rf /var/lib/apt/lists/* \
    && python3 -m venv /opt/verifier-venv \
    && /opt/verifier-venv/bin/pip install --no-cache-dir --no-deps \
        iniconfig==2.3.0 \
        packaging==26.2 \
        pluggy==1.6.0 \
        Pygments==2.20.0 \
        pytest==8.4.1 \
        pytest-json-ctrf==0.5.2

WORKDIR /app
COPY task_file/ /app/
RUN mkdir -p /app/output
CMD ["sleep", "infinity"]
