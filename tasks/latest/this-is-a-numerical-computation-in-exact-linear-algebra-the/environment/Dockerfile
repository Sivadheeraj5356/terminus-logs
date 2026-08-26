FROM public.ecr.aws/docker/library/rust:1.85-slim@sha256:9f841bbe9e7d8e37ceb96ed907265a3a0df7f44e3737d0b100e7907a679acb36

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        make \
        python3 \
        python3-pytest \
        tmux \
        asciinema \
    && rm -rf /var/lib/apt/lists/* \
    && ln -sf /usr/local/cargo/bin/cargo /usr/local/bin/cargo \
    && ln -sf /usr/local/cargo/bin/rustc /usr/local/bin/rustc \
    && ln -sf /usr/local/cargo/bin/rustup /usr/local/bin/rustup \
    && ln -sf /usr/local/cargo/bin/rustfmt /usr/local/bin/rustfmt

WORKDIR /app

COPY Makefile README.md ./
COPY data ./data
COPY docs ./docs
COPY examples ./examples
