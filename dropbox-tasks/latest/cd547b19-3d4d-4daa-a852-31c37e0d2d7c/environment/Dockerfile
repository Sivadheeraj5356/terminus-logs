FROM public.ecr.aws/docker/library/python:3.13-slim-bookworm@sha256:01f42367a0a94ad4bc17111776fd66e3500c1d87c15bbd6055b7371d39c124fb

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tmux \
        asciinema \
        g++ \
        cmake \
        ninja-build \
        jq \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN python -m pip install --no-cache-dir \
    pytest==8.4.1 \
    pytest-json-ctrf==0.3.5

WORKDIR /app

COPY CMakeLists.txt /app/environment/CMakeLists.txt
COPY build_defs /app/environment/build_defs
COPY tools /app/environment/tools
COPY src /app/environment/src
COPY idl /app/environment/idl
COPY include /app/environment/include
COPY abi /app/environment/abi
COPY profiles /app/environment/profiles
COPY runbook /app/environment/runbook
COPY docs /app/environment/docs
COPY README.md /app/environment/README.md

RUN find /app/environment/runbook -type f -name '*.sh' -exec sed -i 's/\r$//' {} + \
    && find /app/environment/runbook -type f -name '*.sh' -exec chmod +x {} +
