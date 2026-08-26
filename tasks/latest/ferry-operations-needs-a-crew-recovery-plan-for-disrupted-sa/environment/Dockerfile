FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac

ENV PATH="/usr/local/go/bin:${PATH}"
ENV GOCACHE=/tmp/gocache
ENV GOPATH=/tmp/go

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-pip tmux asciinema \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.lock /tmp/requirements.lock
RUN pip3 install --break-system-packages --no-cache-dir --require-hashes \
    -r /tmp/requirements.lock

COPY task_file /app/task_file
RUN mkdir -p /app/task_file/output_data
