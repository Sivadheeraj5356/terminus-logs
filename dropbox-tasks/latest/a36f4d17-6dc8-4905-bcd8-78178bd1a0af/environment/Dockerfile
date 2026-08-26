FROM public.ecr.aws/docker/library/ruby:3.3-slim-bookworm@sha256:e76733e94b3a5893e4a141024ef3a583dc10781dc24becebf74f9c9f9a33e3df
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    tmux=3.3a-3 \
    asciinema=2.2.0-1 \
    python3=3.11.2-1+b1 \
    python3-pip=23.0.1+dfsg-1 \
    && rm -rf /var/lib/apt/lists/*

RUN pip3 install --no-cache-dir --break-system-packages \
    pytest==8.4.1 \
    pytest-json-ctrf==0.3.5

RUN gem install bundler -v 2.5.23 --no-document && \
    gem install toml -v 0.3.0 --no-document

COPY . /app/environment/

ENV RUBYLIB=/app/environment:/app/environment/qcl:/app/environment/q9:/app/environment/m2:/app/environment/f5:/app/environment/engine:/app/environment/util:/app/environment/tools
