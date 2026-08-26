FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        asciinema \
        ca-certificates \
        python3 \
        python3-venv \
        tmux \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.lock /tmp/requirements.lock
RUN python3 -m venv /opt/verifier \
    && /opt/verifier/bin/pip install --no-cache-dir --require-hashes --no-deps \
        -r /tmp/requirements.lock \
    && rm /tmp/requirements.lock

ENV PATH="/opt/verifier/bin:${PATH}"
WORKDIR /app

# The Go toolchain stays available because both the agent and verifier rebuild the edited source.
COPY --chmod=0755 build.sh /app/build.sh
COPY link-model.md /app/link-model.md
COPY src/ /app/src/
COPY linkcase/ /app/linkcase/

RUN /app/build.sh
