# Edition 2 canonical Rust builder (public.ecr.aws/docker/library/rust:1.85-slim).
FROM --platform=linux/amd64 public.ecr.aws/docker/library/rust:1.85-slim@sha256:9f841bbe9e7d8e37ceb96ed907265a3a0df7f44e3737d0b100e7907a679acb36 AS rust-builder
WORKDIR /tmp/cargo_warm

# Final runtime uses the canonical Edition 2 Python image because the verifier is a
# pytest suite that must run natively; the canonical Rust toolchain (cargo/rustc) is
# copied in from the builder above so the agent still compiles the release binary
# offline in-image. A pure Rust final image cannot host the pytest verifier.
FROM --platform=linux/amd64 public.ecr.aws/docker/library/python:3.13-slim-bookworm@sha256:01f42367a0a94ad4bc17111776fd66e3500c1d87c15bbd6055b7371d39c124fb
WORKDIR /app

ENV PATH="/opt/verifier/bin:/usr/local/cargo/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
ENV RUSTUP_HOME=/usr/local/rustup
ENV CARGO_HOME=/usr/local/cargo
ENV CARGO_NET_OFFLINE=true
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get -o Acquire::Retries=3 update -qq \
    && apt-get install -y -qq --no-install-recommends \
        asciinema=2.2.0-1 \
        build-essential=12.9 \
        ca-certificates=20230311+deb12u1 \
        file=1:5.44-3 \
        python-is-python3=3.11.2-1+deb12u1 \
        python3=3.11.2-1+b1 \
        python3-pip=23.0.1+dfsg-1 \
        python3-venv=3.11.2-1+b1 \
        tmux=3.3a-3 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=rust-builder /usr/local/cargo /usr/local/cargo
COPY --from=rust-builder /usr/local/rustup /usr/local/rustup

RUN ln -sf /usr/bin/python3 /usr/local/bin/python \
    && ln -sf /usr/local/cargo/bin/cargo /usr/local/bin/cargo \
    && ln -sf /usr/local/cargo/bin/rustc /usr/local/bin/rustc \
    && ln -sf /usr/local/cargo/bin/rustup /usr/local/bin/rustup \
    && ln -sf /usr/local/cargo/bin/cargo /usr/bin/cargo \
    && ln -sf /usr/local/cargo/bin/rustc /usr/bin/rustc \
    && ln -sf /usr/local/cargo/bin/rustup /usr/bin/rustup

COPY requirements.txt /tmp/requirements.txt
RUN python3 -m venv /opt/verifier \
    && /opt/verifier/bin/pip install --no-cache-dir -r /tmp/requirements.txt
RUN rm -f /tmp/requirements.txt

COPY task_file/ /app/task_file/
COPY desiccator_tray_src/ /app/desiccator_tray_src/

RUN mkdir -p /app/bin /app/output

CMD ["bash"]
