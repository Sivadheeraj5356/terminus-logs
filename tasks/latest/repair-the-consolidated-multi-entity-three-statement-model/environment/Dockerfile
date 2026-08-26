FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac

ENV GOTOOLCHAIN=local \
    GOFLAGS=-mod=mod \
    GOCACHE=/tmp/.gocache \
    GOPATH=/tmp/.gopath \
    PATH=/opt/venv/bin:$PATH

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tmux \
        asciinema \
        python3 \
        python3-venv \
        python-is-python3 \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv \
    && pip install --no-cache-dir \
        pytest==8.4.1 \
        pytest-json-ctrf==0.3.5

WORKDIR /app
COPY app/ /app/

RUN cd /app && go build -o /tmp/three_statement . && rm -f /tmp/three_statement
