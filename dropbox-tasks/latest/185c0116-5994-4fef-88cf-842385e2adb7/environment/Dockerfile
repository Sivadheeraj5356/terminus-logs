FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac

WORKDIR /app

ENV DEBIAN_FRONTEND=noninteractive

# verifier-bake-v2: offline pytest via hash-locked requirements.lock
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates=20230311+deb12u1 \
    python3=3.11.2-1+b1 \
    python3-pip=23.0.1+dfsg-1 \
    python3-venv=3.11.2-1+b1 \
    patch=2.7.6-7 \
    tmux=3.3a-3 \
    asciinema=2.2.0-1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.lock /tmp/requirements.txt
RUN python3 -m venv /opt/verifier
RUN /opt/verifier/bin/pip install --no-cache-dir --require-hashes --no-deps -r /tmp/requirements.txt
RUN rm -f /tmp/requirements.txt

ENV PATH=/opt/verifier/bin:/usr/local/go/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
ENV GOPATH=/go

RUN ln -sf /usr/local/go/bin/go /usr/local/bin/go \
    && ln -sf /usr/local/go/bin/gofmt /usr/local/bin/gofmt \
    && ln -sf /opt/verifier/bin/pytest /usr/local/bin/pytest \
    && printf '%s\n' \
      'export PATH=/opt/verifier/bin:/usr/local/go/bin:$PATH' \
      > /etc/profile.d/mx_path.sh

RUN mkdir -p /app/environment /app/output/stage

WORKDIR /app/environment

# Agent-visible tree only. Do not COPY tests/ or solution/.
# Go toolchain retained: weld_bin.sh rebuilds mxbin after agent fixes (runtime compile).
COPY go.mod ./
COPY cmd/ cmd/
COPY a6/ a6/
COPY b2/ b2/
COPY c9/ c9/
COPY docs/ docs/
COPY fixtures/ fixtures/
COPY corpus/ corpus/
COPY scripts/ scripts/
COPY tools/ tools/
COPY .dockerignore .dockerignore

RUN chmod +x /app/environment/scripts/weld_bin.sh \
    /app/environment/scripts/recover.sh \
    /app/environment/tools/mx_run.sh \
    && mkdir -p /app/environment/bin \
    && go build -o /app/environment/bin/mxbin ./cmd/mxbin

WORKDIR /app
CMD ["bash", "-lc", "echo Environment ready"]
