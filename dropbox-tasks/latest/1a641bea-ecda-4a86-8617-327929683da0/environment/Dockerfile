FROM public.ecr.aws/docker/library/eclipse-temurin:21-jdk-jammy@sha256:25d1276565738d3c805e632a4542c3a7598866ef967f4def6544c15de3a74b14

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        bash \
        tmux \
        asciinema \
        util-linux \
        git \
        ripgrep \
        patch \
        ca-certificates \
        python3 \
        python3-pip \
    && rm -rf /var/lib/apt/lists/*

# Verifier-only dependencies, pinned.
COPY requirements.lock /tmp/requirements.lock
RUN pip install --no-cache-dir -r /tmp/requirements.lock \
    && rm -f /tmp/requirements.lock

WORKDIR /app
COPY repo/ /app/

# Make the runtime shim executable and warm the toolchain so the first compile
# after an edit stays fast. The warm output is discarded so no stale classes are
# left behind in the image.
RUN chmod +x /app/bundleresolve \
    && javac -d /tmp/warm-classes /app/Main.java \
    && rm -rf /tmp/warm-classes

RUN git init -q \
    && git config user.email task@example.com \
    && git config user.name task \
    && git config --global --add safe.directory /app \
    && git add -A \
    && git commit -q -m "initial task state"
