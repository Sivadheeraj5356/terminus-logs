FROM public.ecr.aws/docker/library/gcc:13-bookworm@sha256:930f2ebe239275fa67226654cb79273ea34eee672ae61c8a39f689c37fb7ac5c

WORKDIR /app

COPY requirements.lock /tmp/requirements.lock
RUN apt-get update -qq && \
    apt-get install -y -qq --no-install-recommends \
      python3 python3-venv ca-certificates curl psmisc tmux asciinema && \
    python3 -m venv /opt/verifier-venv && \
    /opt/verifier-venv/bin/pip install --no-cache-dir --require-hashes --no-deps -r /tmp/requirements.lock && \
    rm -rf /var/lib/apt/lists/*

COPY task_file/input_data/ /app/input_data/
COPY task_file/scripts/ /app/scripts/
COPY task_file/docs/ /app/docs/
COPY task_file/src/ /app/src/
COPY task_file/thermo/ /app/thermo/

WORKDIR /app
