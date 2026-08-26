# syntax=docker/dockerfile:1.7
# Scala 3 stdlib only build list computer for the modverse module ecosystem.
# Build marker: r7

############################
# Stage 1: fetch and checksum the Scala 3 distribution (build time network only)
############################
FROM public.ecr.aws/docker/library/eclipse-temurin:21-jdk-jammy@sha256:25d1276565738d3c805e632a4542c3a7598866ef967f4def6544c15de3a74b14 AS scaladist

ARG SCALA_VERSION=3.4.2
ARG SCALA_SHA256=2447f095126c6532a4d0300896c87e5350e8ce6e14417c1578b4a4348187304b

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /dist
RUN curl -fsSL -o scala3.tar.gz \
        "https://github.com/scala/scala3/releases/download/${SCALA_VERSION}/scala3-${SCALA_VERSION}.tar.gz" \
    && echo "${SCALA_SHA256}  scala3.tar.gz" | sha256sum -c -

############################
# Stage 2: pure python wheel cache for the offline verifier venv
############################
FROM public.ecr.aws/docker/library/python:3.13-slim-bookworm@sha256:01f42367a0a94ad4bc17111776fd66e3500c1d87c15bbd6055b7371d39c124fb AS pywheels
RUN python -m pip install --no-cache-dir --upgrade pip==24.3.1 wheel==0.45.1
RUN mkdir -p /opt/wheels \
    && pip download --no-cache-dir --dest /opt/wheels \
        pytest==8.4.1 \
        pytest-json-ctrf==0.3.5 \
        exceptiongroup==1.2.2 \
        tomli==2.0.1

############################
# Stage 3: runtime image the agent and verifier exec into
############################
FROM public.ecr.aws/docker/library/eclipse-temurin:21-jdk-jammy@sha256:25d1276565738d3c805e632a4542c3a7598866ef967f4def6544c15de3a74b14

ENV DEBIAN_FRONTEND=noninteractive \
    SCALA_HOME=/opt/scala3 \
    SOURCE_DATE_EPOCH=1700000000 \
    PATH=/opt/scala3/bin:/opt/java/openjdk/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        procps \
        tmux \
        asciinema \
        python3 \
        python3-venv \
    && rm -rf /var/lib/apt/lists/*

# Scala 3 toolchain. The agent needs scalac at runtime because this is a write
# code task. Carry the SHA verified tarball from the builder, unpack it here, and
# remove the archive in the same layer.
ARG SCALA_VERSION=3.4.2
COPY --from=scaladist /dist/scala3.tar.gz /tmp/scala3.tar.gz
RUN tar -xzf /tmp/scala3.tar.gz -C /opt \
    && mv "/opt/scala3-${SCALA_VERSION}" /opt/scala3 \
    && rm -f /tmp/scala3.tar.gz

# Offline baked pytest environment used by every milestone verifier. test.sh
# invokes /opt/test-env/bin/python directly; nothing is installed at runtime.
COPY --from=pywheels /opt/wheels /opt/wheels
RUN python3 -m venv /opt/test-env \
    && /opt/test-env/bin/pip install --no-cache-dir --no-index --find-links /opt/wheels \
        pytest==8.4.1 \
        pytest-json-ctrf==0.3.5 \
    && /opt/test-env/bin/pytest --version

WORKDIR /app

# Project tree: skeleton sources, sample registry, build and run helpers, docs.
COPY --chmod=0755 app/build.sh /app/app/build.sh
COPY --chmod=0755 app/modverse /app/app/modverse
COPY --chmod=0755 app/examples/quickstart.sh /app/app/examples/quickstart.sh
COPY app/src /app/app/src
COPY app/docs /app/app/docs
COPY app/sample-registry /app/app/sample-registry
COPY app/README.md /app/app/README.md

RUN printf '#!/bin/bash\nset -e\nexec /app/app/modverse "$@"\n' > /usr/local/bin/modverse \
    && chmod 0755 /usr/local/bin/modverse \
    && mkdir -p /app/app/build/classes

# No build time warm compile: the oracle and every verifier cold compile from
# source via /app/app/build.sh, so the image ships sources only and never bakes a
# compiled classes tree as a layer.

LABEL org.opencontainers.image.source="https://example.com/modverse-build-resolver" \
      org.opencontainers.image.title="modverse-build-resolver" \
      org.opencontainers.image.description="Scala 3 stdlib only build list computer for a fictional module ecosystem, built over four milestones." \
      org.opencontainers.image.revision="r7" \
      org.opencontainers.image.version="1.0.6"
