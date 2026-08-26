# Final agent image — ground-truth-free artifacts only
FROM public.ecr.aws/docker/library/python:3.13-slim-bookworm@sha256:01f42367a0a94ad4bc17111776fd66e3500c1d87c15bbd6055b7371d39c124fb

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates=20230311+deb12u1 \
    graphviz=2.42.2-7+deb12u1 \
    tmux=3.3a-3 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pendulum_recovery/report.py /app/report.py
COPY pendulum_recovery/schema.sql /app/schema.sql
COPY pendulum_recovery/requirements.txt /app/requirements.txt
COPY pendulum_recovery/README.md /app/README.md
COPY pendulum_recovery/pendulum_captures.duckdb /app/pendulum_captures.duckdb

RUN mkdir -p /opt/seed /app/environment/pendulum_recovery \
    && cp /app/pendulum_captures.duckdb /opt/seed/pendulum_captures.duckdb \
    && chmod 0444 /opt/seed/pendulum_captures.duckdb \
    && ln -sf /app/report.py /app/environment/pendulum_recovery/report.py \
    && ln -sf /app/schema.sql /app/environment/pendulum_recovery/schema.sql \
    && ln -sf /app/README.md /app/environment/pendulum_recovery/README.md

RUN python -m pip install --no-cache-dir -r /app/requirements.txt
RUN python -m pip install --no-cache-dir \
    asciinema==2.4.0 \
    pytest==8.4.1 \
    pytest-json-ctrf==0.3.5
