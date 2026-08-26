# R has no canonical Terminal-Bench base image; this task uses the canonical Python runtime for the pinned pytest verifier and installs pinned Debian R only to run /app/analysis.R.
FROM public.ecr.aws/docker/library/python:3.13-slim-bookworm@sha256:01f42367a0a94ad4bc17111776fd66e3500c1d87c15bbd6055b7371d39c124fb

RUN apt-get update -qq && \
    apt-get install -y --no-install-recommends \
      tmux=3.3a-3 \
      asciinema=2.2.0-1 \
      strace=6.1-0.1 \
      r-base-core=4.2.2.20221110-2 \
      ca-certificates=20230311+deb12u1 && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

WORKDIR /app
RUN mkdir -p /app/data /app/outputs

COPY data/ /app/data/
COPY analysis.R /app/analysis.R
COPY run_analysis_guarded.sh /app/run_analysis_guarded.sh
RUN chmod 0755 /app/run_analysis_guarded.sh
