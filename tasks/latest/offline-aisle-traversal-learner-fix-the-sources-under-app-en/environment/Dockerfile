FROM public.ecr.aws/docker/library/rust:1.85-slim@sha256:9f841bbe9e7d8e37ceb96ed907265a3a0df7f44e3737d0b100e7907a679acb36

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3=3.11.2-1+b1 \
    python3-pip=23.0.1+dfsg-1 \
    python3-venv=3.11.2-1+b1 \
    tmux=3.3a-3 \
    asciinema=2.2.0-1 \
    ca-certificates=20230311+deb12u1 \
    patch=2.7.6-7 \
    && rm -rf /var/lib/apt/lists/*

# Install pytest tooling into /opt/verifier. Symlink onto /usr/local/bin so
# Harbor login shells that reset PATH still find pytest.
RUN python3 -m venv /opt/verifier \
    && /opt/verifier/bin/pip install --no-cache-dir \
        pytest==8.4.1 \
        pytest-json-ctrf==0.3.5 \
        pytest-randomly==3.16.0 \
        tomli==2.0.1

# Harbor login shells can reset PATH; keep pytest/cargo on /usr/local/bin.
RUN ln -sf /opt/verifier/bin/pytest /usr/local/bin/pytest \
    && ln -sf /opt/verifier/bin/python /usr/local/bin/python3-verifier \
    && ln -sf /usr/local/cargo/bin/cargo /usr/local/bin/cargo \
    && ln -sf /usr/local/cargo/bin/rustc /usr/local/bin/rustc

ENV PATH=/opt/verifier/bin:${PATH}
ENV CARGO_HOME=/opt/cargo
ENV CARGO_TARGET_DIR=/tmp/cargo-target

RUN mkdir -p /app/output /app/bin /logs/verifier /opt/cargo /tmp/cargo-target

COPY . /app/environment

RUN ln -sfn /app/environment/fixtures /app/fixtures \
    && ln -sfn /app/environment/spec /app/spec \
    && ln -sfn /app/environment/docs /app/docs \
    && chmod +x /app/environment/tools/rebuild_bin.sh \
    && cargo build --release --manifest-path /app/environment/Cargo.toml \
    && cp /tmp/cargo-target/release/lane_matrix /app/bin/lane_matrix

CMD ["python3", "-c", "print('Environment ready')"]
