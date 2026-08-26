FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac

ENV GOTOOLCHAIN=local \
    CGO_ENABLED=0 \
    TZ=UTC \
    PATH=/app/bin:/usr/local/go/bin:${PATH}

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        asciinema=2.2.0-1 \
        ca-certificates=20230311+deb12u1 \
        jq=1.6-2.1+deb12u2 \
        make=4.3-4.1 \
        patch=2.7.6-7 \
        python3=3.11.2-1+b1 \
        python3-pytest=7.2.1-2 \
        socat=1.7.4.4-2 \
        tmux=3.3a-3 \
    && ln -sf /usr/bin/python3 /usr/bin/python \
    && rm -rf /var/lib/apt/lists/*

COPY app/ /app/
RUN make build
