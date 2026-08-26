FROM public.ecr.aws/docker/library/rust:1.85-slim@sha256:9f841bbe9e7d8e37ceb96ed907265a3a0df7f44e3737d0b100e7907a679acb36

ENV LANG=C.UTF-8

RUN apt-get update && apt-get install -y --no-install-recommends \
        units \
        make \
        tmux \
        asciinema \
        python3 \
        python3-pip \
        ca-certificates \
        curl \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.lock /tmp/requirements.lock
RUN python3 -m pip install --no-cache-dir --break-system-packages \
        --require-hashes --no-deps -r /tmp/requirements.lock

# `bash -lc` starts a login shell, which resets PATH from /etc/profile and drops the
# rust image's CARGO_HOME/bin. Put it back for every shell, and symlink the toolchain.
RUN printf 'export PATH=/usr/local/cargo/bin:$PATH\n' > /etc/profile.d/cargo.sh \
 && chmod 0644 /etc/profile.d/cargo.sh \
 && ln -sf /usr/local/cargo/bin/cargo /usr/local/bin/cargo \
 && ln -sf /usr/local/cargo/bin/rustc /usr/local/bin/rustc \
 && ln -sf /usr/local/cargo/bin/rustup /usr/local/bin/rustup

WORKDIR /app/tariff
COPY tariff/Cargo.toml .
COPY tariff/Cargo.lock .
COPY tariff/Makefile .
COPY tariff/src ./src
RUN mkdir -p .cargo \
 && cargo vendor --locked vendor > .cargo/config.toml \
 && CARGO_NET_OFFLINE=true cargo build --offline --locked --release

COPY data/ /app/data/
COPY spec/ /app/spec/
WORKDIR /app
