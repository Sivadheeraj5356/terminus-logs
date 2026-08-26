FROM public.ecr.aws/docker/library/python:3.13-slim-bookworm@sha256:01f42367a0a94ad4bc17111776fd66e3500c1d87c15bbd6055b7371d39c124fb

WORKDIR /app

# Install system dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        asciinema \
        ca-certificates \
        cargo rustc \
        git \
        tmux \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies (PIN VERSIONS!)
RUN pip install --no-cache-dir \
    numpy==2.3.5 pandas==2.3.3 requests==2.32.4 \
    pytest==8.2.0 pytest-json-ctrf==0.5.2

# Copy task files
COPY app/ /app/

# Set up environment
ENV PYTHONPATH=/app
