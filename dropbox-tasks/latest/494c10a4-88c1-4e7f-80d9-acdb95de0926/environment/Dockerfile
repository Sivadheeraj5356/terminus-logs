FROM public.ecr.aws/docker/library/rust:1.85-slim@sha256:9f841bbe9e7d8e37ceb96ed907265a3a0df7f44e3737d0b100e7907a679acb36

RUN printf 'Acquire::Retries "5";\n' > /etc/apt/apt.conf.d/80-retries \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        make tmux asciinema python3 python3-pytest \
    && rm -rf /var/lib/apt/lists/*

RUN ln -sf /usr/local/cargo/bin/rustc /usr/local/bin/rustc \
    && ln -sf /usr/local/cargo/bin/cargo /usr/local/bin/cargo

WORKDIR /app
COPY src /app/src
COPY Makefile /app/Makefile
COPY data /app/data
COPY docs /app/docs
