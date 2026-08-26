FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac

LABEL org.opencontainers.image.title="optimize-quantum-state-simulation" \
    org.opencontainers.image.source="https://github.com/laude-institute/terminal-bench" \
    org.opencontainers.image.revision="1.0.0" \
    org.opencontainers.image.created="2026-07-13T00:00:00Z" \
    org.opencontainers.image.version="1.0.0" \
    org.opencontainers.image.licenses="MIT"

ENV DEBIAN_FRONTEND=noninteractive \
    GOTOOLCHAIN=local \
    GO111MODULE=on \
    CGO_ENABLED=0 \
    PATH="/go/bin:/usr/local/go/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin" \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

COPY requirements.txt /tmp/requirements.txt

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        asciinema=2.2.0-1 \
        ca-certificates=20230311+deb12u1 \
        make=4.3-4.1 \
        passwd \
        python3=3.11.2-1+b1 \
        python3-pip=23.0.1+dfsg-1 \
        tmux=3.3a-3 \
        util-linux \
    && pip3 install --break-system-packages --no-cache-dir -r /tmp/requirements.txt \
    && ln -sf /usr/bin/python3 /usr/bin/python \
    && rm -rf /var/lib/apt/lists/* /root/.cache /tmp/requirements.txt

WORKDIR /app

# Keep default USER as root so Harbor can run tests/test.sh as root.
# Grading still builds/runs qwavectl as the restricted `model` user via runuser.
RUN /usr/sbin/useradd --create-home --uid 10001 --shell /bin/bash model \
    && mkdir -p /app/build /home/model/go/cache /home/model/tmp \
    && chown model:model /app /app/build /home/model /home/model/go /home/model/go/cache /home/model/tmp

COPY --chown=model:model go.mod Makefile /app/
COPY --chown=model:model wavefn_corpus/ /app/wavefn_corpus/
COPY --chown=model:model engine_spec/ /app/engine_spec/
COPY --chown=model:model qwavectl/ /app/qwavectl/
COPY --chown=model:model ampstore/ /app/ampstore/
COPY --chown=model:model gatekron/ /app/gatekron/
COPY --chown=model:model circexec/ /app/circexec/
COPY --chown=model:model numpolicy/ /app/numpolicy/
