FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac

ENV DEBIAN_FRONTEND=noninteractive \
    GOTOOLCHAIN=local \
    GO111MODULE=on \
    CGO_ENABLED=0 \
    PATH=/usr/local/go/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        asciinema=2.2.0-1 \
        ca-certificates=20230311+deb12u1 \
        make=4.3-4.1 \
        python3=3.11.2-1+b1 \
        python3-pip=23.0.1+dfsg-1 \
        tmux=3.3a-3 \
    && pip3 install --break-system-packages --no-cache-dir \
        pytest==8.4.1 \
        pytest-json-ctrf==0.3.5 \
    && rm -rf /var/lib/apt/lists/* /root/.cache

WORKDIR /app

COPY go.mod Makefile /app/
COPY feature-policy/ /app/feature-policy/
COPY crate-captures/ /app/crate-captures/
COPY preflight-gates/ /app/preflight-gates/
COPY featurectl/ /app/featurectl/
COPY cargograph/ /app/cargograph/

RUN chmod +x /app/preflight-gates/preflight.sh \
    && chmod 444 /app/crate-captures/.capture_guard \
    && ln -s /app/crate-captures /app/work-captures \
    && mkdir -p /app/build \
    && go version \
    && test -x /usr/local/go/bin/go
