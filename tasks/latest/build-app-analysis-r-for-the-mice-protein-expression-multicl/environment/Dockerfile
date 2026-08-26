FROM public.ecr.aws/docker/library/python:3.13-slim-bookworm@sha256:01f42367a0a94ad4bc17111776fd66e3500c1d87c15bbd6055b7371d39c124fb
# Python runs the pytest-based checks; R is installed for the submitted analysis.
WORKDIR /app
RUN apt-get update -qq && apt-get install -y --no-install-recommends tmux asciinema r-base-core r-cran-jsonlite ca-certificates bash && rm -rf /var/lib/apt/lists/*
RUN python3 -m venv /opt/test-venv
COPY requirements.lock /tmp/requirements.lock
RUN /opt/test-venv/bin/pip install --no-cache-dir --only-binary=:all: --require-hashes -r /tmp/requirements.lock
RUN mkdir -p /app/data /app/config /app/docs /app/outputs
COPY data/ /app/data/
COPY config/ /app/config/
COPY docs/ /app/docs/
