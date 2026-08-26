FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac

WORKDIR /app

ENV PATH="/usr/local/go/bin:${PATH}"

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        asciinema=2.2.0-1 \
        ca-certificates=20230311+deb12u1 \
        python3=3.11.2-1+b1 \
        python3-pip=23.0.1+dfsg-1 \
        python3-venv=3.11.2-1+b1 \
        tmux=3.3a-3 \
    && rm -rf /var/lib/apt/lists/*

RUN ln -sf /usr/local/go/bin/go /usr/local/bin/go \
    && ln -sf /usr/local/go/bin/gofmt /usr/local/bin/gofmt \
    && python3 -m venv /opt/verifier-venv \
    && /opt/verifier-venv/bin/pip install --no-cache-dir \
        iniconfig==2.3.0 \
        packaging==26.2 \
        pluggy==1.6.0 \
        pygments==2.20.0 \
        pytest==8.4.1 \
        pytest-json-ctrf==0.3.5

COPY task_file/ /app/task_file/

RUN mkdir -p /app/out
