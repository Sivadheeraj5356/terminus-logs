# Single-stage build on the digest-pinned canonical Temurin JDK image.
FROM public.ecr.aws/docker/library/eclipse-temurin:21-jdk-jammy@sha256:25d1276565738d3c805e632a4542c3a7598866ef967f4def6544c15de3a74b14

ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        python3 \
        python3-pip \
        python3-venv \
        curl \
        unzip \
        asciinema \
        ca-certificates \
        git \
        patch \
        ripgrep \
        sed \
        tmux \
        util-linux \
    && rm -rf /var/lib/apt/lists/*

# Install the official Kotlin command-line compiler.
ARG KOTLIN_VERSION=2.0.20
ARG KOTLIN_SHA256=5f5d2a8ad6a718a002acd0775b67a9e27035872fdbd4b0791e3cb3ea00095931
RUN curl -fsSL -o /tmp/kotlin.zip "https://github.com/JetBrains/kotlin/releases/download/v${KOTLIN_VERSION}/kotlin-compiler-${KOTLIN_VERSION}.zip" \
    && echo "${KOTLIN_SHA256}  /tmp/kotlin.zip" | sha256sum -c - \
    && unzip -q /tmp/kotlin.zip -d /opt \
    && ln -s /opt/kotlinc/bin/kotlinc /usr/local/bin/kotlinc \
    && rm /tmp/kotlin.zip

# Debian/Ubuntu system Python is externally managed; install the verifier deps
# into a virtualenv on PATH so `python`/`pip` resolve to it (verifier runs
# non-login).
RUN python3 -m venv /opt/venv
ENV PATH=/opt/venv/bin:${PATH}

COPY requirements.lock /tmp/requirements.lock
RUN pip install --no-cache-dir -r /tmp/requirements.lock

WORKDIR /app

COPY repo/ /app/

# Warm the compiler so the agent's rebuild is incremental.
RUN kotlinc /app/Selgate.kt -include-runtime -d /app/selgate.jar || true

RUN kotlinc /app/Selgate.kt -include-runtime -d /app/selgate.jar \
    && git init -q \
    && git config user.email task@example.com \
    && git config user.name task \
    && git add -A \
    && git commit -q -m "initial task state" \
    && tmux -V \
    && asciinema --version \
    && python -m pytest --version
