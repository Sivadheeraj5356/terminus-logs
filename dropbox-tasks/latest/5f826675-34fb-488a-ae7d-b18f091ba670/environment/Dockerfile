# Python 3.13 on Debian bookworm (slim), pinned by digest. The final runtime
# base is the canonical Terminal-Bench Python image; the Dart SDK (not on the
# canonical list) is added on top and verified by checksum below.
FROM public.ecr.aws/docker/library/python:3.13-slim-bookworm@sha256:01f42367a0a94ad4bc17111776fd66e3500c1d87c15bbd6055b7371d39c124fb

WORKDIR /app

# Terminal/session utilities plus the fetch tools used once to install the SDK.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        asciinema=2.2.0-1 \
        ca-certificates=20230311+deb12u1 \
        curl=7.88.1-10+deb12u14 \
        tmux=3.3a-3 \
        unzip=6.0-28 \
    && rm -rf /var/lib/apt/lists/*

# Dart SDK: pinned by version and verified by SHA-256 before extraction.
ARG DART_VERSION=3.5.4
ARG DART_SHA256=8d0c5e34f2a9d6b9f5ebf05252ae1703893f6087d547c631b390aef2d0cd6967
RUN curl -fsSL "https://storage.googleapis.com/dart-archive/channels/stable/release/${DART_VERSION}/sdk/dartsdk-linux-x64-release.zip" -o /tmp/dartsdk.zip \
    && echo "${DART_SHA256}  /tmp/dartsdk.zip" | sha256sum -c - \
    && unzip -q /tmp/dartsdk.zip -d /usr/lib \
    && rm /tmp/dartsdk.zip \
    && ln -s /usr/lib/dart-sdk/bin/dart /usr/local/bin/dart
# Put the SDK on PATH; the symlink above also exposes `dart` on the default PATH
# so non-login shells (and the verifier's subprocess) always find it.
ENV PATH="/usr/lib/dart-sdk/bin:${PATH}"

# Python test dependencies, pinned by hash (see requirements.txt).
COPY requirements.txt /tmp/requirements.txt
RUN pip install --require-hashes --no-cache-dir -r /tmp/requirements.txt \
    && rm /tmp/requirements.txt

# Well inputs.
COPY data/ /app/data/

# Fail the build early if the Dart toolchain is missing.
RUN dart --version
