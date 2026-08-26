FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac

ENV DEBIAN_FRONTEND=noninteractive

RUN echo 'export PATH="/usr/local/go/bin:$PATH"' > /etc/profile.d/golang-path.sh \
    && ln -sf /usr/local/go/bin/go /usr/local/bin/go \
    && ln -sf /usr/local/go/bin/gofmt /usr/local/bin/gofmt

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        python3=3.11.2-1+b1 \
        curl=7.88.1-10+deb12u14 \
        ca-certificates=20230311+deb12u1 \
        tmux=3.3a-3 \
        asciinema=2.2.0-1 \
    && curl -fsSL https://astral.sh/uv/0.9.5/install.sh -o /tmp/uv-installer.sh \
    && echo "8402ab80d2ef54d7044a71ea4e4e1e8db3b20c87c7bffbc30bff59f1e80ebbd5  /tmp/uv-installer.sh" | sha256sum -c - \
    && sh /tmp/uv-installer.sh \
    && rm /tmp/uv-installer.sh \
    && rm -rf /var/lib/apt/lists/* \
    && ln -sf /usr/bin/python3 /usr/bin/python

ENV PATH="/usr/local/go/bin:/root/.local/bin:${PATH}"
ENV UV_CACHE_DIR="/root/.cache/uv"

RUN uv python install 3.13 \
    && uvx -p 3.13 -w pytest==8.4.1 -w pytest-json-ctrf==0.3.5 -w crc32c==2.7.1 pytest --version

ENV UV_OFFLINE=1

WORKDIR /app/environment
COPY go.mod go.sum ./
RUN go mod download

COPY cmd ./cmd
COPY internal ./internal
COPY configs ./configs
COPY data ./data
COPY docs ./docs
COPY fixtures ./fixtures
COPY ci ./ci
COPY notes ./notes
COPY README.md ./

RUN uvx -p 3.13 -w crc32c==2.7.1 -- python ci/gen_fixtures.py \
    && mkdir -p /app/bin /app/out /app/var /logs/verifier \
    && go build -o /app/bin/claimdocketaudit ./cmd/claimdocketaudit

WORKDIR /app
