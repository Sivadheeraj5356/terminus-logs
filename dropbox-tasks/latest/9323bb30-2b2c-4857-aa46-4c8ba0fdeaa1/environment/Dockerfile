FROM public.ecr.aws/docker/library/debian:bookworm-slim@sha256:4724b8cc51e33e398f0e2e15e18d5ec2851ff0c2280647e1310bc1642182655d AS builder

WORKDIR /build
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        ca-certificates \
        curl \
    && rm -rf /var/lib/apt/lists/*

ENV RUSTUP_HOME=/usr/local/rustup CARGO_HOME=/usr/local/cargo
RUN curl -fsSL https://sh.rustup.rs -o /var/cache/rustup.sh \
    && sh /var/cache/rustup.sh -y --default-toolchain 1.85.0 --profile minimal \
    && rm -f /var/cache/rustup.sh
ENV PATH="/usr/local/cargo/bin:${PATH}"

WORKDIR /build/app
COPY app/Cargo.toml app/Cargo.lock ./
RUN mkdir -p src/bin \
    && printf 'fn main(){}\n' > src/bin/kvtile_plan.rs \
    && cp src/bin/kvtile_plan.rs src/bin/kvtile_advance.rs \
    && cp src/bin/kvtile_plan.rs src/bin/kvtile_seal.rs \
    && printf 'pub fn _stub(){}\n' > src/lib.rs \
    && cargo fetch --locked

FROM public.ecr.aws/docker/library/debian:bookworm-slim@sha256:4724b8cc51e33e398f0e2e15e18d5ec2851ff0c2280647e1310bc1642182655d

LABEL org.opencontainers.image.title="rust-flashattn-kvtile-block-residency-gate"
LABEL org.opencontainers.image.licenses="MIT"

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        asciinema \
        bubblewrap \
        build-essential \
        ca-certificates \
        python3 \
        python3-pip \
        python3-venv \
        tmux \
        util-linux \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-verifier.txt /var/cache/requirements-verifier.txt
RUN python3 -m venv /opt/verifier-venv \
    && /opt/verifier-venv/bin/pip install --no-cache-dir -r /var/cache/requirements-verifier.txt \
    && rm -f /var/cache/requirements-verifier.txt

COPY --from=builder /usr/local/cargo /usr/local/cargo
COPY --from=builder /usr/local/rustup /usr/local/rustup
RUN ln -sf /usr/local/cargo/bin/cargo /usr/bin/cargo \
    && ln -sf /usr/local/cargo/bin/rustc /usr/bin/rustc
ENV PATH="/usr/local/cargo/bin:/app/bin:/usr/bin:${PATH}"
ENV RUSTUP_HOME=/usr/local/rustup CARGO_HOME=/usr/local/cargo

WORKDIR /app
COPY app/ /app/

RUN mkdir -p /app/bin /app/data /app/output /app/var \
    && chmod +x /app/scripts/build.sh /app/scripts/rebuild.sh /app/scripts/write-compiler-epoch.sh \
    && sed -i 's/\r$//' /app/scripts/build.sh /app/scripts/rebuild.sh /app/scripts/write-compiler-epoch.sh \
    && cargo build --release --locked \
    && install -m 0755 /app/target/release/kvtile-plan /app/bin/kvtile-plan \
    && install -m 0755 /app/target/release/kvtile-advance /app/bin/kvtile-advance \
    && install -m 0755 /app/target/release/kvtile-seal /app/bin/kvtile-seal

ENV PATH="/app/bin:/usr/local/cargo/bin:/usr/bin:${PATH}"
ENV TZ=UTC

CMD ["bash"]
