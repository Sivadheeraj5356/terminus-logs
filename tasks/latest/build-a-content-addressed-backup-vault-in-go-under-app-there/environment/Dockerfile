FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac

ENV DEBIAN_FRONTEND=noninteractive \
    GOTOOLCHAIN=local \
    GOPROXY=off \
    GOFLAGS=-mod=mod \
    CGO_ENABLED=0 \
    PATH="/usr/local/go/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

RUN ln -sf /usr/local/go/bin/go /usr/local/bin/go \
    && ln -sf /usr/local/go/bin/gofmt /usr/local/bin/gofmt

COPY requirements.lock /tmp/requirements.lock

RUN printf 'Acquire::http::Timeout "120";\nAcquire::Retries "3";\n' > /etc/apt/apt.conf.d/99timeout \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        asciinema \
        ca-certificates \
        python-is-python3 \
        python3 \
        python3-pip \
        tmux \
    && python3 -m pip install --no-cache-dir --break-system-packages \
        --require-hashes --no-deps -r /tmp/requirements.lock \
    && PY_BIN="$(readlink -f /usr/bin/python3)" \
    && cp "$PY_BIN" /opt/verifier-python3 \
    && ln -sf /opt/verifier-python3 /opt/verifier-python \
    && rm -f /usr/bin/python3 /usr/bin/python3.* /usr/bin/pip3 /usr/bin/pip \
    && if [ -f /usr/bin/asciinema ]; then \
         sed -i '1s|^#!.*python3.*|#!/opt/verifier-python3|' /usr/bin/asciinema; \
       fi \
    && rm -rf /var/lib/apt/lists/* /tmp/requirements.lock \
    && mkdir -p /tmp/.harbor-tmux && chmod 1777 /tmp/.harbor-tmux

WORKDIR /app

COPY go.mod /app/go.mod
COPY spec/ /app/spec/
COPY data/ /app/data/

# Job trees must survive packaging that drops *.tmp / empty dirs (e.g. create_task_zip).
# Recreate exclude-only fixtures and require every manifest job src before chmod.
RUN set -eux; \
    mkdir -p \
        /app/data/jobs/baseline/src \
        /app/data/jobs/sparse-primary/src \
        /app/data/jobs/cross-job-alpha/src \
        /app/data/jobs/cross-job-beta/src \
        /app/data/jobs/symlink-pack/src/links \
        /app/data/jobs/hardlink-cluster/src/hard \
        /app/data/jobs/exclude-heavy/src/nested \
        /app/data/jobs/empty_job/src \
        /app/data/jobs/quarantine-hit/src \
        /app/data/jobs/zero-byte-pack/src \
        /app/data/jobs/deep-nest/src/a/b/c/d \
        /app/bin /app/output /app/resources; \
    printf 'x' > /app/data/jobs/empty_job/src/only.tmp; \
    printf 'should-exclude' > /app/data/jobs/exclude-heavy/src/drop.tmp; \
    : > /app/data/jobs/symlink-pack/src/links/.keep; \
    test -f /app/data/manifest.json; \
    test -f /app/data/jobs/empty_job/backup_config.json; \
    test -d /app/data/jobs/empty_job/src; \
    test -f /app/data/jobs/empty_job/src/only.tmp; \
    test -f /app/data/jobs/exclude-heavy/src/keep.txt; \
    test -f /app/data/jobs/exclude-heavy/src/drop.tmp; \
    test -f /app/data/jobs/symlink-pack/src/real.txt; \
    test -f /app/data/jobs/hardlink-cluster/src/hard/a; \
    ln -sfn ../real.txt /app/data/jobs/symlink-pack/src/links/to-real; \
    rm -f /app/data/jobs/hardlink-cluster/src/hard/b; \
    ln /app/data/jobs/hardlink-cluster/src/hard/a /app/data/jobs/hardlink-cluster/src/hard/b; \
    test -L /app/data/jobs/symlink-pack/src/links/to-real; \
    test "$(stat -c '%i' /app/data/jobs/hardlink-cluster/src/hard/a)" = \
         "$(stat -c '%i' /app/data/jobs/hardlink-cluster/src/hard/b)"; \
    find /app/spec /app/data -type f -exec chmod a-w {} +; \
    find /app/spec /app/data -depth -type d -exec chmod a-w {} +
