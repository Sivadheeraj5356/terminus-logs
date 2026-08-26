FROM public.ecr.aws/docker/library/python:3.13-slim-bookworm@sha256:01f42367a0a94ad4bc17111776fd66e3500c1d87c15bbd6055b7371d39c124fb

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential tmux asciinema && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --require-hashes --no-deps -r /tmp/requirements.txt

COPY Makefile /app/environment/Makefile
COPY include/ /app/environment/include/
COPY src/ /app/environment/src/
COPY scripts/ /app/environment/scripts/
COPY docs/ /app/environment/docs/
COPY data/ /app/environment/data/

WORKDIR /app/environment
