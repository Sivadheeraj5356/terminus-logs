FROM public.ecr.aws/docker/library/python:3.13-slim-bookworm@sha256:01f42367a0a94ad4bc17111776fd66e3500c1d87c15bbd6055b7371d39c124fb

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONDONTWRITEBYTECODE=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        default-jdk-headless \
        ca-certificates \
        tmux \
        asciinema \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.lock /tmp/requirements.lock
RUN pip install --no-cache-dir --require-hashes --no-deps -r /tmp/requirements.lock

WORKDIR /app

COPY starter/Main.java /app/Main.java
COPY docs/CONTRACT.md /app/docs/CONTRACT.md
COPY data /app/data
COPY run.sh /app/run.sh

RUN chmod +x /app/run.sh \
    && mkdir -p /app/out \
    && javac -d /app/out /app/Main.java
