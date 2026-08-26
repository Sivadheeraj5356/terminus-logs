# Non-canonical Go toolchain image: t-bench registry has no Go 1.24 base; digest-pinned for reproducibility.
FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac

COPY requirements.lock /tmp/requirements.lock

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        git \
        tmux \
        asciinema \
        python3 \
        python3-venv \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && python3 -m venv /opt/verifier \
    && /opt/verifier/bin/pip install --no-cache-dir --upgrade pip==25.0.1 \
    && /opt/verifier/bin/pip install --no-cache-dir \
        -r /tmp/requirements.lock --require-hashes --no-deps \
    && rm -f /tmp/requirements.lock

ENV PATH="/usr/local/go/bin:/opt/verifier/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
ENV GOTOOLCHAIN=local
ENV GIT_PAGER=cat

RUN ln -s /usr/local/go/bin/go /usr/local/bin/go \
    && ln -s /usr/local/go/bin/gofmt /usr/local/bin/gofmt \
    && bash -lc 'command -v go && command -v gofmt && go version'

WORKDIR /app

COPY setup_repo.sh /tmp/setup_repo.sh

RUN chmod +x /tmp/setup_repo.sh \
    && /tmp/setup_repo.sh \
    && rm -f /tmp/setup_repo.sh \
    && find /app -name 'setup_repo.sh' -delete 2>/dev/null || true

RUN mkdir -p /app/reports \
    && git config --global --add safe.directory /app/repo \
    && git config --global core.pager cat
