FROM public.ecr.aws/docker/library/python:3.13-slim-bookworm@sha256:01f42367a0a94ad4bc17111776fd66e3500c1d87c15bbd6055b7371d39c124fb

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        bash \
        ca-certificates \
        curl \
        jq \
        make \
        perl \
        libio-socket-ssl-perl \
        procps \
        tmux \
        asciinema \
    && rm -rf /var/lib/apt/lists/*

RUN python -m pip install --no-cache-dir \
    Flask==3.1.1 \
    flask-cors==6.0.1 \
    Pillow==11.3.0 \
    PyYAML==6.0.2 \
    requests==2.32.4 \
    pytest==8.4.1 \
    pytest-json-ctrf==0.3.5

WORKDIR /app
COPY api ./api
COPY config ./config
COPY fixtures ./fixtures
COPY scripts ./scripts
COPY vendor ./vendor
COPY Makefile openapi.yaml ./
RUN chmod +x scripts/analyze.pl vendor/yq_linux_amd64
