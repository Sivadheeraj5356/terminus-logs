# Canonical base: golang:1.24-bookworm (ci_checks/canonical_base_images.toml).
FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    python3 \
    python3-venv \
    python-is-python3 \
    tmux \
    asciinema \
    && rm -rf /var/lib/apt/lists/* \
    && command -v tmux && command -v asciinema

# Verifier tooling is baked at image build; runtime has allow_internet=false.
COPY wheels /app/wheels
COPY verifier-requirements.txt /opt/verifier/requirements.txt
RUN python -m venv /opt/verifier-venv
RUN /opt/verifier-venv/bin/pip install --no-index --find-links=/app/wheels \
        --no-cache-dir --require-hashes -r /opt/verifier/requirements.txt \
    && /opt/verifier-venv/bin/pytest --version
RUN rm -rf /app/wheels

COPY src/. /app/
COPY data/scenarios.json /app/data/scenarios.json
COPY data/config /app/config
COPY data/fixtures /app/data/fixtures
COPY docs /app/docs

RUN go build -buildvcs=false -o /app/chronctl ./cmd/chronctl \
    && rm -rf /root/.cache/go-build

# chronrun: unprivileged identity used when the verifier invokes agent-controlled
# /app/chronctl inside a /tests-hidden view (mount ns or stash isolation).
RUN useradd -r -s /usr/sbin/nologin chronrun \
    && mkdir -p /app/output \
    && chown chronrun:chronrun /app/output \
    && chmod 0777 /app/output \
    && ln -sf /opt/verifier-venv/bin/pytest /usr/local/bin/pytest \
    && find /app/data /app/config -type f -exec chmod a-w {} + \
    && printf '%s\n' \
        'export PATH="/opt/verifier-venv/bin:/usr/local/go/bin:/app:${PATH}"' \
        > /etc/profile.d/chronctl-path.sh

ENV PATH="/opt/verifier-venv/bin:/usr/local/go/bin:/app:${PATH}"
