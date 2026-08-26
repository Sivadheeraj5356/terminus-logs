FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac

WORKDIR /app
ENV PATH="/opt/verifier-venv/bin:/usr/local/go/bin:${PATH}"

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        asciinema=2.2.0-1 \
        ca-certificates=20230311+deb12u1 \
        python3=3.11.2-1+b1 \
        python-is-python3=3.11.2-1+deb12u1 \
        python3-pip=23.0.1+dfsg-1 \
        python3-venv=3.11.2-1+b1 \
        less=590-2.1~deb12u2 \
        nano=7.2-1+deb12u1 \
        procps=2:4.0.2-3 \
        git=1:2.39.5-0+deb12u3 \
        tmux=3.3a-3 \
    && ln -sf /usr/local/go/bin/go /usr/local/bin/go \
    && ln -sf /usr/local/go/bin/gofmt /usr/local/bin/gofmt \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.lock /tmp/requirements.lock
RUN python3 -m venv /opt/verifier-venv \
    && /opt/verifier-venv/bin/pip install --no-cache-dir --require-hashes --no-deps -r /tmp/requirements.lock \
    && rm -f /tmp/requirements.lock

COPY app/ /app/
RUN rm -rf /app/task_file/bin /app/task_file/output \
    && mkdir -p /app/task_file/bin /app/task_file/output
