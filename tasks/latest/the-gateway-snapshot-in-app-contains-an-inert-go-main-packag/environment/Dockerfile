# The submitted Go program is compiled during offline verification.
FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac

ENV GOTOOLCHAIN=local \
    GOPROXY=off \
    GOFLAGS=-mod=mod \
    CGO_ENABLED=0

COPY requirements.lock /tmp/requirements.lock

RUN apt-get update \
    && apt-get install -y --no-install-recommends tmux asciinema python3 python3-venv strace \
    && rm -rf /var/lib/apt/lists/* \
    && python3 -m venv /opt/verifier-venv \
    && /opt/verifier-venv/bin/pip install --no-cache-dir --only-binary=:all: --require-hashes \
        -r /tmp/requirements.lock

WORKDIR /app
COPY task_file/ /app/
RUN mkdir -p /app/output

CMD ["sleep", "infinity"]
