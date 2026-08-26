FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac

RUN apt-get update -qq \
    && apt-get install -y -qq --no-install-recommends python3 python3-pip python3-venv tmux asciinema \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv /opt/verifier-venv \
    && /opt/verifier-venv/bin/pip install --no-cache-dir pytest==8.4.1 pytest-json-ctrf==0.3.6

WORKDIR /app
COPY task_file/input/ /app/input/
RUN mkdir -p /app/output

CMD ["bash"]
