FROM public.ecr.aws/docker/library/gcc:13-bookworm@sha256:930f2ebe239275fa67226654cb79273ea34eee672ae61c8a39f689c37fb7ac5c

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      ca-certificates \
      python3 \
      python3-venv \
      python3-pip \
      patch \
      electric-fence \
      jq \
      tmux \
      asciinema \
      procps \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /tmp/requirements.txt
RUN python3 -m venv /opt/verifier-venv \
 && /opt/verifier-venv/bin/pip install --no-cache-dir --require-hashes -r /tmp/requirements.txt

WORKDIR /app/environment

COPY . /app/environment/
