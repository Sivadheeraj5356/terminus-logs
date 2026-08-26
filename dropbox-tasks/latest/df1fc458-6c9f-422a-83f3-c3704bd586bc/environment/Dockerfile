FROM public.ecr.aws/docker/library/ruby:3.3-slim-bookworm@sha256:e76733e94b3a5893e4a141024ef3a583dc10781dc24becebf74f9c9f9a33e3df

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        asciinema \
        openssl \
        python3 \
        python3-pip \
        tmux \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --break-system-packages --no-cache-dir pytest==8.4.1 pytest-json-ctrf==0.3.5

COPY app/ /app/
RUN chmod +x /app/bin/kev-ledger
