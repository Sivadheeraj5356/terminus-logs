FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac

ENV DEBIAN_FRONTEND=noninteractive
ENV TERM=xterm
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8
ENV TMUX_TMPDIR=/var/tmp/tmux
ENV PATH=/usr/local/go/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
ENV GOPATH=/go
ENV GOCACHE=/var/cache/cv-go
ENV GOMODCACHE=/var/cache/cv-gomod
ENV GOTOOLCHAIN=local

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    asciinema=2.2.0-1 \
    ca-certificates=20230311+deb12u1 \
    ncurses-term=6.4-4 \
    python3=3.11.2-1+b1 \
    python3-venv=3.11.2-1+b1 \
    tmux=3.3a-3 \
    && mkdir -p /var/tmp/tmux /var/cache/cv-go /var/cache/cv-gomod \
    && chmod 1777 /var/tmp/tmux /var/cache/cv-go /var/cache/cv-gomod \
    && ln -sf /usr/local/go/bin/go /usr/local/bin/go \
    && ln -sf /usr/local/go/bin/gofmt /usr/local/bin/gofmt \
    && printf '%s\n' \
        'export GOPATH=/go' \
        'export GOCACHE=/var/cache/cv-go' \
        'export GOMODCACHE=/var/cache/cv-gomod' \
        'export GOTOOLCHAIN=local' \
        'export PATH=/opt/verifier-venv/bin:/usr/local/go/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin' \
        > /etc/profile.d/task-path.sh \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-verifier.txt /tmp/requirements-verifier.txt
RUN python3 -m venv /opt/verifier-venv \
    && /opt/verifier-venv/bin/pip install --no-cache-dir --require-hashes \
        -r /tmp/requirements-verifier.txt

# Login shells reset PATH; keep pytest/go on durable /usr/local/bin paths.
RUN ln -sf /opt/verifier-venv/bin/pytest /usr/local/bin/pytest \
    && ln -sf /opt/verifier-venv/bin/python /usr/local/bin/python-verifier

ENV PATH=/opt/verifier-venv/bin:/usr/local/go/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

COPY runtime/tmux.conf /etc/tmux.conf
COPY go.mod go.sum /app/environment/
COPY horizon /app/environment/horizon
COPY anchor /app/environment/anchor
COPY ribbon /app/environment/ribbon
COPY splice /app/environment/splice
COPY pulse /app/environment/pulse
COPY lens /app/environment/lens
COPY tablet /app/environment/tablet
COPY harbor /app/environment/harbor
COPY warp /app/environment/warp
COPY filament /app/environment/filament
COPY meridian /app/environment/meridian
COPY beacon /app/environment/beacon
COPY laneio /app/environment/laneio
COPY cmd /app/environment/cmd
COPY docs /app/environment/docs
COPY internal /app/environment/internal
COPY samples /app/environment/samples

WORKDIR /app/environment
RUN go build -o /usr/local/bin/cvctl ./cmd/cvctl

WORKDIR /app
