FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac

ENV DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# verifier deps: pytest==8.4.1 pytest-json-ctrf==0.3.5 (hashed in requirements.lock)

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
    asciinema \
    bash \
    ca-certificates \
    coreutils \
    findutils \
    python3 \
    python3-pip \
    python3-venv \
    tmux \
 && rm -rf /var/lib/apt/lists/* \
 && command -v tmux >/dev/null \
 && tmux -V \
 && command -v asciinema >/dev/null \
 && asciinema --version \
 && command -v go >/dev/null \
 && go version

COPY requirements.lock /tmp/requirements.lock
RUN python3 -m venv /opt/verifier-venv \
 && /opt/verifier-venv/bin/pip install --no-cache-dir --require-hashes -r /tmp/requirements.lock

ENV PATH="/opt/verifier-venv/bin:/usr/local/go/bin:/go/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
RUN printf '%s\n' \
    'export PATH="/opt/verifier-venv/bin:/usr/local/go/bin:/go/bin:$PATH"' \
    > /etc/profile.d/task-runtime.sh

COPY data/ /app/data/
RUN mkdir -p /app/output
