# The agent must rebuild current Go source offline and the final runtime must retain the Go toolchain; the canonical generic runtime images do not provide that compiler.
FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends tmux asciinema python3 python3-pip && rm -rf /var/lib/apt/lists/*
COPY requirements.lock /tmp/requirements.lock
RUN pip3 install --break-system-packages --no-cache-dir --require-hashes --no-deps -r /tmp/requirements.lock && rm /tmp/requirements.lock

COPY app/ /app/
RUN /app/src/build.sh
