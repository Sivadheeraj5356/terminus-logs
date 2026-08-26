FROM public.ecr.aws/docker/library/gcc:13-bookworm@sha256:930f2ebe239275fa67226654cb79273ea34eee672ae61c8a39f689c37fb7ac5c

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        asciinema \
        binutils \
        file \
        libjansson-dev \
        libsqlite3-dev \
        libssl-dev \
        libyaml-dev \
        make \
        python3 \
        python3-venv \
        sqlite3 \
        tmux \
        util-linux \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /tmp/verifier-requirements.txt
RUN python3 -m venv /opt/verifier \
    && /opt/verifier/bin/pip install --no-cache-dir --require-hashes \
        -r /tmp/verifier-requirements.txt \
    && rm -f /tmp/verifier-requirements.txt

ENV PATH="/opt/verifier/bin:${PATH}"
ENV PYTHONDONTWRITEBYTECODE=1

RUN groupadd --gid 10001 candidate \
    && useradd --uid 10001 --gid 10001 --create-home --shell /bin/bash candidate \
    && install -d -o candidate -g candidate /app/mlflow-maze \
    && install -d -o candidate -g candidate /app/mlflow-maze/out

WORKDIR /app/mlflow-maze
COPY --chown=candidate:candidate mlflow-maze/ /app/mlflow-maze/
RUN sqlite3 /app/mlflow-maze/fixtures/tracking.sqlite \
        < /app/mlflow-maze/fixtures/schema.sql \
    && sqlite3 /app/mlflow-maze/fixtures/tracking.sqlite \
        < /app/mlflow-maze/fixtures/seed.sql \
    && chown candidate:candidate /app/mlflow-maze/fixtures/tracking.sqlite \
    && chmod 0755 \
        /app/mlflow-maze/scripts/recover-and-replay.sh \
        /app/mlflow-maze/tools/validate_manifest.py \
    && chmod 0444 \
        /app/mlflow-maze/fixtures/tracking.sqlite \
        /app/mlflow-maze/config/maze.yaml \
        /app/mlflow-maze/config/puzzles.toml \
        /app/mlflow-maze/docs/RECOVERY_CONTRACT.md \
        /app/mlflow-maze/docs/MLFLOW_STORE.md \
        /app/mlflow-maze/schema/level-manifest.schema.json

USER candidate
RUN make clean all

# The verifier remains privileged only to seal /tests and then drops every
# candidate-controlled build or execution to UID 10001.
USER root
ENV HOME=/home/candidate
WORKDIR /app/mlflow-maze
