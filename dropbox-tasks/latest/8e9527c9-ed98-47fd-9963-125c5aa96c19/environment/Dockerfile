FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac

RUN apt-get update && apt-get install -y --no-install-recommends tmux asciinema ca-certificates curl && rm -rf /var/lib/apt/lists/*

RUN curl -LsSf https://astral.sh/uv/0.5.11/install.sh | env UV_INSTALL_DIR=/usr/local/bin sh
RUN uv venv /opt/verifier --python 3.13 \
    && uv pip install --python /opt/verifier/bin/python pytest==8.4.1 pytest-json-ctrf==0.3.5

WORKDIR /app

ENV GOFLAGS=-mod=mod
ENV GOTOOLCHAIN=local

COPY go.mod /app/go.mod
COPY docs/ /app/docs/
COPY cmd/ /app/cmd/
COPY internal/ /app/internal/
COPY data/ /app/data/

RUN go build -o /app/bin/bvm ./cmd/bvm
