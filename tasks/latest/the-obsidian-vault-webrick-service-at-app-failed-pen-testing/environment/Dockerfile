# Justification: We use the official Ruby 3.3 slim image instead of a canonical Ubuntu base
# because this task requires specific Ruby 3.3 features and using the official slim image
# avoids complex custom Ruby compilation steps that would increase build time.
FROM public.ecr.aws/docker/library/ruby:3.3-slim-bookworm@sha256:e76733e94b3a5893e4a141024ef3a583dc10781dc24becebf74f9c9f9a33e3df

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        asciinema \
        build-essential \
        ca-certificates \
        gcc \
        golang-go \
        python3 \
        python3-pip \
        python3-venv \
        tmux \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.lock /tmp/requirements.lock
RUN python3 -m venv /opt/verifier-venv \
    && /opt/verifier-venv/bin/pip install \
        --require-hashes --no-deps --no-cache-dir \
        -r /tmp/requirements.lock

WORKDIR /app

COPY app/Gemfile app/Gemfile.lock ./
COPY prop_test/go.mod prop_test/go.sum ./prop_test/
RUN bundle install --without development && cd /app/prop_test && go mod download

COPY app/config/ ./config/
COPY app/lib/    ./lib/
COPY app/routes/ ./routes/
COPY app/server.rb ./

COPY prop_test/ ./prop_test/
COPY docs/ ./docs/
