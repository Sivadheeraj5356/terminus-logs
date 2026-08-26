# syntax=docker/dockerfile:1

FROM public.ecr.aws/docker/library/python:3.13-slim-bookworm@sha256:01f42367a0a94ad4bc17111776fd66e3500c1d87c15bbd6055b7371d39c124fb

USER root
WORKDIR /app

ENV PATH="/opt/test-venv/bin:${PATH}" \
    PYTHONHASHSEED=0 \
    PYTHONDONTWRITEBYTECODE=1 \
    OMP_NUM_THREADS=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        asciinema \
        bash \
        ca-certificates \
        tmux \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.lock /opt/build/requirements.lock
RUN python3 -m venv /opt/test-venv \
    && /opt/test-venv/bin/pip install --no-cache-dir --require-hashes --no-deps \
        -r /opt/build/requirements.lock \
    && rm -rf /opt/build

COPY app/ /app/
RUN install -d -m 0777 /app/out \
    && test -w /app/out

# Never copy tests/, solution/, rubric.md, or _authoring/ into this image.
