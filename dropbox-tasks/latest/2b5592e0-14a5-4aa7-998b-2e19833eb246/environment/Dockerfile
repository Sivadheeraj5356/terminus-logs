FROM public.ecr.aws/docker/library/python:3.13-slim-bookworm@sha256:01f42367a0a94ad4bc17111776fd66e3500c1d87c15bbd6055b7371d39c124fb

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
        r-base-core \
        tmux \
        asciinema \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /tmp/requirements.txt
RUN python -m pip install --no-cache-dir --require-hashes -r /tmp/requirements.txt

WORKDIR /app
RUN mkdir -p /app/data /app/outputs

COPY data/ /app/data/
COPY contracts/ /app/contracts/
COPY fskit/ /app/fskit/
COPY analysis.R /app/analysis.R
