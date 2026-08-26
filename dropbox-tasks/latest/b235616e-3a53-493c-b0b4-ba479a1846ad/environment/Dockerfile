FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac

COPY --from=ghcr.io/astral-sh/uv:0.9.5@sha256:0f419824ea1810fe2a47af12aef8e8c39eabae8d19c728cd9612d18e17a98d17 /uv /uvx /usr/local/bin/

ENV DEBIAN_FRONTEND=noninteractive
ENV PATH="/usr/local/go/bin:/opt/verifier/bin:/usr/local/bin:${PATH}"
ENV GONOSUMDB="*"
ENV GOFLAGS="-mod=mod"

RUN apt-get update && apt-get install -y --no-install-recommends \
    tmux=3.3a-3 \
    asciinema=2.2.0-1 \
    ca-certificates=20230311+deb12u1 \
    && rm -rf /var/lib/apt/lists/*

COPY verifier-requirements.txt /opt/verifier-requirements.txt
RUN uv venv --python 3.13 /opt/verifier
RUN uv pip install --python=/opt/verifier/bin/python --require-hashes -r /opt/verifier-requirements.txt
RUN /opt/verifier/bin/pytest --version
RUN uvx -p 3.13 --with-requirements /opt/verifier-requirements.txt pytest --version \
    && UV_OFFLINE=1 uvx --offline -p 3.13 --with-requirements /opt/verifier-requirements.txt pytest --version

WORKDIR /app

COPY go.mod /app/go.mod
COPY cmd /app/cmd
COPY internal /app/internal
COPY data /app/data
COPY docs /app/docs
COPY README.md /app/README.md

RUN go build -o /app/bin/bayctl /app/cmd/bayctl \
    && mkdir -p /app/output /app/state /logs/agent \
    && test ! -d /app/solution \
    && test ! -d /app/tests \
    && test ! -f /app/solve.sh \
    && test ! -f /app/instruction.md \
    && test ! -f /app/task.toml

ENV TEST_DIR=/tests

CMD ["sleep", "infinity"]
