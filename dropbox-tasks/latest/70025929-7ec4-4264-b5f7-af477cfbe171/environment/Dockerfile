# Final runtime base image for the task environment.
FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac

WORKDIR /app

ENV DEBIAN_FRONTEND=noninteractive

# verifier-bake-v2: offline pytest + TypeScript toolchain baked into the image
RUN apt-get update && apt-get install -y --no-install-recommends asciinema ca-certificates npm patch python3 python3-pip python3-venv tmux && rm -rf /var/lib/apt/lists/*

COPY wheels /tmp/wheels
RUN python3 -m venv /opt/verifier-venv
RUN /opt/verifier-venv/bin/pip install --no-cache-dir --no-index --find-links=/tmp/wheels pytest==8.4.1 pytest-json-ctrf==0.3.5 pytest-randomly==3.16.0
RUN rm -rf /tmp/wheels \
    && mkdir -p /opt/verifier/bin \
    && ln -sfn /opt/verifier-venv/bin/pytest /opt/verifier/bin/pytest \
    && test -x /opt/verifier/bin/pytest \
    && /opt/verifier/bin/pytest --version

COPY x7/m2/k81/package.json x7/m2/k81/package-lock.json /app/environment/x7/m2/k81/
COPY x7/m2/k81/offline /app/environment/x7/m2/k81/offline
RUN cd /app/environment/x7/m2/k81 && npm install --offline --no-audit --no-fund --no-package-lock ./offline/typescript-5.7.2.tgz ./offline/types-node-22.10.2.tgz ./offline/undici-types-6.20.0.tgz && rm -rf offline /root/.npm

COPY . /app/environment

RUN chmod +x /app/environment/scripts/build_all.sh && cd /app/environment && ./scripts/build_all.sh && rm -rf /app/environment/wheels /app/environment/x7/m2/k81/offline && mkdir -p /app/output

ENV PATH="/opt/verifier/bin:/usr/local/go/bin:/opt/verifier-venv/bin:/app/environment/bin:${PATH}"
