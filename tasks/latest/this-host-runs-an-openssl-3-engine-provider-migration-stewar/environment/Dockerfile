FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac

LABEL org.opencontainers.image.source="https://github.com/laude-institute/terminal-bench"
LABEL org.opencontainers.image.revision="openssl-engine-provider-migration"
LABEL org.opencontainers.image.created="2026-07-14"
LABEL org.opencontainers.image.version="1.0.0"
LABEL org.opencontainers.image.licenses="Apache-2.0"

WORKDIR /app

ENV PATH="/opt/verifier/bin:/usr/local/go/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
ENV PYTHONNOUSERSITE=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV OV_ROOT=/app/environment

RUN apt-get update && apt-get install -y --no-install-recommends \
    openssl=3.0.20-1~deb12u2 \
    libssl3=3.0.20-1~deb12u2 \
    asciinema=2.2.0-1 \
    python3=3.11.2-1+b1 \
    python3-venv=3.11.2-1+b1 \
    tmux=3.3a-3 \
    util-linux=2.38.1-5+deb12u3 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /tmp/requirements.txt
RUN python3 -m venv /opt/verifier \
    && sed -i 's/\r$//' /tmp/requirements.txt \
    && /opt/verifier/bin/pip install --no-cache-dir --require-hashes --no-deps \
        -r /tmp/requirements.txt \
    && ln -sf /opt/verifier/bin/pytest /usr/local/bin/pytest \
    && ln -sf /opt/verifier/bin/python /usr/local/bin/pytest-python

# Privilege split: verifier (root) owns /opt/verifier and /logs/verifier.
# Submitted probe/build paths run as unprivileged 'agent' via runuser.
RUN useradd --create-home --uid 1000 --shell /bin/bash agent \
    && mkdir -p /logs/verifier /opt/verifier/guard /app/output \
    && chmod 700 /logs/verifier \
    && chown agent:agent /app/output

COPY --chown=agent:agent . /app/environment

# Root-owned snapshots of frozen baselines — agent may write live paths, verifier compares.
RUN mkdir -p /opt/verifier/ref_blobs \
    && cp /app/environment/share/ref_blobs/ord.go /opt/verifier/ref_blobs/ord.go \
    && cp /app/environment/share/ref_blobs/bind.go /opt/verifier/ref_blobs/bind.go \
    && sha256sum /opt/verifier/ref_blobs/ord.go /opt/verifier/ref_blobs/bind.go \
        > /opt/verifier/ref_blobs.sha256 \
    && chmod 444 /opt/verifier/ref_blobs/ord.go /opt/verifier/ref_blobs/bind.go \
                 /opt/verifier/ref_blobs.sha256 \
    && chown root:root /opt/verifier/ref_blobs /opt/verifier/ref_blobs/ord.go \
                       /opt/verifier/ref_blobs/bind.go /opt/verifier/ref_blobs.sha256

RUN find /app/environment -type f -name '*.sh' -exec sed -i 's/\r$//' {} + \
    && sed -i 's/\r$//' /app/environment/tools/ov_probe/ov_probe \
    && chmod +x /app/environment/tools/ov_probe/ov_probe \
    && chmod +x /app/environment/scripts/build_workspace.sh \
    && chmod +x /app/environment/migrations/rst9.sh \
    && chmod +x /app/environment/q8/legacy.sh \
    && chmod +x /app/environment/r4/stub.sh \
    && chmod +x /app/environment/t6/decoy.sh \
    && runuser -u agent -- bash /app/environment/scripts/build_workspace.sh

WORKDIR /app
CMD ["bash", "-lc", "echo Environment ready"]
