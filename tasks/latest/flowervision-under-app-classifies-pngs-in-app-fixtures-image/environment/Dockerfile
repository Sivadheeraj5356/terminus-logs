# Python base image hosts the offline pytest verifier venv; Ruby/ImageMagick/Redis are apt packages for the agent workload.
FROM public.ecr.aws/docker/library/python:3.13-slim-bookworm@sha256:01f42367a0a94ad4bc17111776fd66e3500c1d87c15bbd6055b7371d39c124fb

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tmux \
        asciinema \
        ruby \
        ruby-dev \
        build-essential \
        redis-server \
        imagemagick \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY Gemfile Gemfile.lock /app/
RUN gem install bundler:2.5.23 --no-document \
    && bundle config set --local path 'vendor/bundle' \
    && bundle config set --local without 'development' \
    && bundle install --deployment

COPY verifier/requirements.lock /tmp/verifier-requirements.lock
RUN python -m venv /app/.tbench-testing \
    && /app/.tbench-testing/bin/pip install --no-cache-dir pip==24.3.1 \
    && /app/.tbench-testing/bin/pip install --no-cache-dir --require-hashes -r /tmp/verifier-requirements.lock \
    && rm /tmp/verifier-requirements.lock

COPY . /app

# Seed deterministic PNG fixtures with ImageMagick (no external downloads)
RUN mkdir -p /app/fixtures/images /app/tmp /app/output /app/log \
    && convert -size 64x64 xc:'#e87070' /app/fixtures/images/flower001.png \
    && convert -size 80x48 xc:'#70e880' /app/fixtures/images/rose001.png \
    && convert -size 96x96 xc:'#7090e8' /app/fixtures/images/daisy002.png \
    && convert -size 120x90 xc:'#e8d070' /app/fixtures/images/tulip003.png \
    && convert -size 55x55 xc:'#c070e8' /app/fixtures/images/violet004.png \
    && chmod +x /app/bin/rails \
    && chmod +x /app/scripts/*.rb

ENV BUNDLE_PATH=/app/vendor/bundle \
    REDIS_URL=redis://127.0.0.1:6379/0 \
    RACK_ENV=production \
    PORT=3000 \
    PATH="/app/bin:${PATH}"

WORKDIR /app
