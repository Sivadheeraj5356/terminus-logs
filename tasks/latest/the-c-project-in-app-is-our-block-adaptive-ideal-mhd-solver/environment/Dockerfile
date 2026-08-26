# Canonical Terminal-Bench Ubuntu base image (digest-pinned). The task is a self-contained
# C++17 project built with the system GNU toolchain; the verifier drives the compiled binary
# from Python with numpy.
FROM public.ecr.aws/docker/library/ubuntu:24.04@sha256:0d39fcc8335d6d74d5502f6df2d30119ff4790ebbb60b364818d5112d9e3e932

ENV DEBIAN_FRONTEND=noninteractive

# Agent runtime needs tmux + asciinema; g++/make build the project; python3 + numpy drive the
# verifier. Everything is resolved in a single apt transaction from the pinned base snapshot.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        asciinema \
        ca-certificates \
        g++ \
        make \
        python3 \
        python3-numpy \
        python3-pip \
        tmux \
    && rm -rf /var/lib/apt/lists/*

# Verifier-only Python dependencies, pinned. pytest-json-ctrf has no apt package.
RUN pip install --no-cache-dir --break-system-packages \
        pytest==8.3.4 \
        pytest-json-ctrf==0.3.5

COPY app/ /app/

WORKDIR /app
