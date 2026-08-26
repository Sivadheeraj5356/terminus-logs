FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac

ENV PATH="/usr/local/go/bin:/go/bin:${PATH}" \
    GOTOOLCHAIN=local \
    GOPROXY=off \
    CGO_ENABLED=0

RUN test -x /usr/local/go/bin/go \
    && test -x /usr/local/go/bin/gofmt \
    && ln -s /usr/local/go/bin/go /usr/local/bin/go \
    && ln -s /usr/local/go/bin/gofmt /usr/local/bin/gofmt \
    && /usr/local/bin/go version

RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-venv tmux asciinema ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.lock /tmp/requirements.lock
RUN python3 -m venv /opt/verifier-venv \
    && /opt/verifier-venv/bin/pip install --no-cache-dir --disable-pip-version-check \
        --require-hashes --no-deps -r /tmp/requirements.lock \
    && rm /tmp/requirements.lock

WORKDIR /app/task_file
COPY task_file/ /app/task_file/
RUN mkdir -p /app/task_file/output

CMD ["sleep", "infinity"]
