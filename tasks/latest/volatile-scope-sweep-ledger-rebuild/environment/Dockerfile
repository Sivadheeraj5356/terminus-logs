FROM public.ecr.aws/docker/library/rust:1.85-slim@sha256:9f841bbe9e7d8e37ceb96ed907265a3a0df7f44e3737d0b100e7907a679acb36

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends python3=3.11.2-1+b1 python3-pytest=7.2.1-2 tmux=3.3a-3 asciinema=2.2.0-1 ca-certificates=20230311+deb12u1 && rm -rf /var/lib/apt/lists/*

COPY . /app/environment

RUN cd /app/environment && cargo build --release
