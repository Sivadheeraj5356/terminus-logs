FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac

WORKDIR /app

RUN ln -sf /usr/local/go/bin/go /usr/local/bin/go \
    && ln -sf /usr/local/go/bin/gofmt /usr/local/bin/gofmt

ENV GOPATH=/go

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates=20230311+deb12u1 \
    bash=5.2.15-2+b13 \
    curl=7.88.1-10+deb12u14 \
    file=1:5.44-3 \
    python3=3.11.2-1+b1 \
    tmux=3.3a-3 \
    asciinema=2.2.0-1 \
    && rm -rf /var/lib/apt/lists/*

ARG UV_INSTALL_SHA256=8402ab80d2ef54d7044a71ea4e4e1e8db3b20c87c7bffbc30bff59f1e80ebbd5
RUN curl -fsSL -o /tmp/uv-install.sh https://astral.sh/uv/0.9.5/install.sh \
    && echo "${UV_INSTALL_SHA256}  /tmp/uv-install.sh" | sha256sum -c - \
    && sh /tmp/uv-install.sh \
    && rm -f /tmp/uv-install.sh

ENV PATH="/root/.local/bin:${PATH}"

RUN uv venv /opt/verifier-venv --python 3.13 \
    && PATH="/opt/verifier-venv/bin:${PATH}" uv pip install \
        pytest==8.4.1 \
        pytest-json-ctrf==0.3.5 \
        pytest-order==1.3.0 \
        pytest-dependency==0.6.0

ENV VIRTUAL_ENV=/opt/verifier-venv
ENV PATH="/opt/verifier-venv/bin:${PATH}"
ENV UV_OFFLINE=1

COPY go.mod /app/go.mod
COPY cfg /app/cfg
COPY data /app/data
COPY doc /app/doc
COPY cmd /app/cmd
COPY internal /app/internal
COPY launcher /app/launcher
COPY notes /app/notes
COPY resources /app/resources
COPY scripts /app/scripts
COPY stubs /app/stubs
COPY tools /app/tools

RUN chmod +x /app/launcher/cl_publish /app/scripts/compile_report.sh \
    && mkdir -p /app/output /app/bin /logs/agent /logs/verifier \
    && chmod 777 /logs/agent /logs/verifier /app/output
