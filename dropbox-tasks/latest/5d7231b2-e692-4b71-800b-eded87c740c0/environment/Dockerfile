# Canonical Terminal-Bench Node.js runtime base (PLATFORM_AUTO_EVAL.md Node.js family).
FROM public.ecr.aws/docker/library/node:22-bookworm-slim@sha256:f3a68cf41a855d227d1b0ab832bed9749469ef38cf4f58182fb8c893bc462383
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3=3.11.2-1+b1 \
    python3-venv=3.11.2-1+b1 \
    ca-certificates=20230311+deb12u1 \
    patch=2.7.6-7 \
    tmux=3.3a-3 \
    asciinema=2.2.0-1 \
    && rm -rf /var/lib/apt/lists/*

COPY verifier-reqs /tmp/requirements.txt
RUN python3 -m venv /opt/verifier \
    && /opt/verifier/bin/pip install --no-cache-dir --require-hashes -r /tmp/requirements.txt

ENV PATH=/opt/verifier/bin:${PATH}
RUN ln -sf /opt/verifier/bin/pytest /usr/local/bin/pytest

COPY package.json /app/environment/package.json
COPY n4 /app/environment/n4
COPY r8 /app/environment/r8
COPY t2 /app/environment/t2
COPY tools /app/environment/tools
COPY scripts /app/environment/scripts
COPY ops /app/environment/ops
COPY data /app/environment/data
COPY fixtures /app/environment/fixtures
COPY guide /app/environment/guide

RUN mkdir -p /app/output/traces /app/output/stage \
    && chmod +x /app/environment/tools/drv_k7/drv_k7.js \
    && chmod +x /app/environment/scripts/build_all.sh \
    && chmod +x /app/environment/ops/rst7.sh \
    && chmod +x /app/environment/t2/y5/src/main.js
WORKDIR /app
