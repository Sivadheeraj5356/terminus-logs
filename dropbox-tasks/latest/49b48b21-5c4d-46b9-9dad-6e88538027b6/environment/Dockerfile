FROM public.ecr.aws/docker/library/python:3.13-slim-bookworm@sha256:01f42367a0a94ad4bc17111776fd66e3500c1d87c15bbd6055b7371d39c124fb

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    bash \
    tmux \
    asciinema \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir pytest==8.4.1 pytest-json-ctrf==0.3.5

ENV PYTHONPATH=/app
ENV PYTHONDONTWRITEBYTECODE=1

COPY cfg /app/cfg
COPY data /app/data
COPY doc /app/doc
COPY eng /app/eng
COPY launcher /app/launcher
COPY scripts /app/scripts
COPY stubs /app/stubs

RUN chmod +x /app/launcher/lf_align /app/scripts/frontier.sh \
    && mkdir -p /app/output
