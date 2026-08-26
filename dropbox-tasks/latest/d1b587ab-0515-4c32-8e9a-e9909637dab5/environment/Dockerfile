FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac

ENV DEBIAN_FRONTEND=noninteractive
ENV PATH="/usr/local/go/bin:${PATH}"

# tmux and asciinema are required agent-runtime packages. They are installed
# from the digest-pinned base image under the project runtime-package exception.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        asciinema \
        ca-certificates \
        python-is-python3 \
        python3 \
        python3-pip \
        tmux \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /tmp/requirements.txt
RUN python -m pip install --no-cache-dir --break-system-packages --require-hashes -r /tmp/requirements.txt \
    && rm -f /tmp/requirements.txt

COPY app/ /app/
WORKDIR /app

RUN test "$(command -v go)" = "/usr/local/go/bin/go" \
    && test "$(command -v chroot)" = "/usr/sbin/chroot" \
    && go version \
    && test "$(command -v gofmt)" = "/usr/local/go/bin/gofmt" \
    && python --version \
    && python -m pytest --version \
    && python -m pytest --help | grep -q -- "--ctrf"
