# Canonical Maven row: docs/PLATFORM_AUTO_EVAL.md (maven:3.9.9-eclipse-temurin-21).
FROM public.ecr.aws/docker/library/maven:3.9.9-eclipse-temurin-21@sha256:3a4ab3276a087bf276f79cae96b1af04f53731bec53fb2e651aca79e4b10211e

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3=3.12.3-0ubuntu2.1 \
    python3-venv=3.12.3-0ubuntu2.1 \
    python3-pip=24.0+dfsg-1ubuntu1.3 \
    ca-certificates=20260601~24.04.1 \
    tmux=3.4-1ubuntu0.1 \
    asciinema=2.4.0-1 \
    patch=2.7.6-7build3 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.in /tmp/requirements.in
RUN python3 -m venv /opt/verifier \
    && /opt/verifier/bin/pip install --no-cache-dir --require-hashes --no-deps \
        -r /tmp/requirements.in
ENV PATH=/opt/verifier/bin:${PATH}

COPY . /app/environment/

RUN chmod +x /app/environment/scripts/*.sh /app/environment/migrations/*.sh \
    && mkdir -p /app/output /app/environment/kit/scratch /app/environment/bin \
    && bash /app/environment/scripts/build_all.sh \
    && test -x /app/environment/bin/og_check
