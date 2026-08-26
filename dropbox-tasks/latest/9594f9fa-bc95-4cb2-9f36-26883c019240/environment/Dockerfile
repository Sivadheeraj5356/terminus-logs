FROM public.ecr.aws/docker/library/debian:bookworm-slim@sha256:4724b8cc51e33e398f0e2e15e18d5ec2851ff0c2280647e1310bc1642182655d

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
        gnat libgnatcoll21-dev make tmux asciinema python3 python3-pip \
        git ca-certificates patch \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.lock /tmp/requirements.lock
RUN pip3 install --no-cache-dir --break-system-packages --require-hashes --no-deps -r /tmp/requirements.lock

WORKDIR /app
COPY repo/ /app/

RUN mkdir -p /app/build \
    && git init -q \
    && git config user.email task@example.com \
    && git config user.name task \
    && git add -A \
    && GIT_AUTHOR_DATE="2026-05-09T09:00:00Z" GIT_COMMITTER_DATE="2026-05-09T09:00:00Z" \
       git commit -q -m "initial task state"
