FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac

ENV DEBIAN_FRONTEND=noninteractive \
    PATH=/usr/local/go/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
    GOTOOLCHAIN=local \
    GO111MODULE=on \
    CGO_ENABLED=0 \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        asciinema=2.2.0-1 \
        ca-certificates=20230311+deb12u1 \
        make=4.3-4.1 \
        python3=3.11.2-1+b1 \
        python3-pip=23.0.1+dfsg-1 \
        tmux=3.3a-3 \
    && rm -rf /var/lib/apt/lists/* /root/.cache

COPY verifier-deps.lock /tmp/verifier-deps.lock
RUN pip3 install --break-system-packages --no-cache-dir -r /tmp/verifier-deps.lock \
    && rm -f /tmp/verifier-deps.lock

COPY go.mod Makefile /app/
COPY semver-spec/ /app/semver-spec/
COPY release-graphs/ /app/release-graphs/
COPY grading-overrides/ /opt/svis-fixtures/grading-overrides/
COPY probe-scripts/ /app/probe-scripts/
COPY impact-engine/ /app/impact-engine/
COPY propagation/ /app/propagation/
COPY contracts/ /app/contracts/

RUN mkdir -p /app/build
