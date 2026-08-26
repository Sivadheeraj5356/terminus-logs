# The canonical Python base is required because the verifier runs pytest; apt supplies the C++17 toolchain.
FROM public.ecr.aws/docker/library/python:3.13-slim-bookworm@sha256:01f42367a0a94ad4bc17111776fd66e3500c1d87c15bbd6055b7371d39c124fb
RUN apt-get update && apt-get install -y --no-install-recommends g++ make libboost-dev tmux asciinema && rm -rf /var/lib/apt/lists/*
COPY requirements.lock /tmp/requirements.lock
RUN python3 -m pip install --no-cache-dir --require-hashes --no-deps -r /tmp/requirements.lock
WORKDIR /app
COPY Makefile /app/Makefile
COPY src/ /app/src/
COPY docs/ /app/docs/
