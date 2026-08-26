FROM public.ecr.aws/docker/library/python:3.13-slim-bookworm@sha256:01f42367a0a94ad4bc17111776fd66e3500c1d87c15bbd6055b7371d39c124fb

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      build-essential \
      gcc \
      g++ \
      make \
      ca-certificates \
      tmux \
      asciinema \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /tmp/requirements.txt
RUN python3 -m venv /opt/verifier-venv \
 && /opt/verifier-venv/bin/pip install --no-cache-dir --require-hashes -r /tmp/requirements.txt

WORKDIR /app/environment

COPY Makefile /app/environment/Makefile
COPY include /app/environment/include
COPY src /app/environment/src
COPY cmd /app/environment/cmd
COPY examples /app/environment/examples
COPY docs /app/environment/docs
COPY testdata /app/environment/testdata
COPY requirements.txt /app/environment/requirements.txt

WORKDIR /app/environment
