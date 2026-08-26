# Canonical Go runtime, pinned by digest. The verifier builds the candidate at test time.
FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac
ENV GOCACHE=/tmp/go-build
ENV GOPATH=/tmp/go
ENV GOTOOLCHAIN=local
ENV CGO_ENABLED=0

RUN ln -sf /usr/local/go/bin/go /usr/local/bin/go \
    && ln -sf /usr/local/go/bin/gofmt /usr/local/bin/gofmt \
    && printf 'export PATH=$PATH:/usr/local/go/bin\n' > /etc/profile.d/go.sh

WORKDIR /app

# tmux + asciinema are required by the agent runtime; python3 + python3-pytest drive the
# verifier with no pip and no network (the stdlib referee needs nothing else).
RUN apt-get update -o Acquire::Retries=10 \
    && apt-get install -y --no-install-recommends \
        tmux \
        asciinema \
        python3 \
        python3-pytest \
        util-linux \
    && rm -rf /var/lib/apt/lists/*
RUN python3 -m pytest --version

COPY app/ /app/
