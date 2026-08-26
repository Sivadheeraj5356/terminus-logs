FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        asciinema=2.2.0-1 \
        ca-certificates=20230311+deb12u1 \
        tmux=3.3a-3 \
        gcc=4:12.2.0-3 \
        libc6-dev=2.36-9+deb12u14 \
        libsqlite3-dev=3.40.1-2+deb12u2 \
        sqlite3=3.40.1-2+deb12u2 \
        python3=3.11.2-1+b1 \
        python3-pip=23.0.1+dfsg-1 \
        python3-venv=3.11.2-1+b1 \
    && rm -rf /var/lib/apt/lists/*

COPY auth/go.mod auth/go.sum /app/auth/
COPY auth/cmd/ /app/auth/cmd/
COPY auth/internal/ /app/auth/internal/
COPY auth/tools/ /app/auth/tools/
RUN cd /app/auth && go mod download

COPY verifier-requirements.lock /tmp/verifier-requirements.lock
RUN python3 -m venv /opt/runtime-venv \
    && /opt/runtime-venv/bin/pip install --require-hashes --no-deps --no-cache-dir \
        -r /tmp/verifier-requirements.lock

COPY auth/config/ /app/auth/config/
COPY auth/docs/ /app/auth/docs/
COPY auth/keys/rotation-state.json /app/auth/keys/
COPY auth/migrations/ /app/auth/migrations/
COPY auth/bin/ /app/auth/bin/
COPY auth/scripts/ /app/auth/scripts/

RUN chmod +x /app/auth/bin/*.sh /app/auth/scripts/image-init.sh \
    && /app/auth/scripts/image-init.sh

WORKDIR /app
