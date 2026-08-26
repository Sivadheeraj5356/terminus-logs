FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac

ENV DEBIAN_FRONTEND=noninteractive
ENV PATH="/usr/local/go/bin:${PATH}"

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
      asciinema \
      ca-certificates \
      curl \
      git \
      procps \
      python3 \
      python3-venv \
      tmux \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.lock /tmp/requirements.lock
RUN python3 -m venv /opt/verifier-venv \
    && /opt/verifier-venv/bin/pip install --no-cache-dir -r /tmp/requirements.lock

WORKDIR /opt/bottleplan/app
COPY task_file/ /
RUN mkdir -p /opt/bottleplan/app/bin /var/lib/bottleplan/out
