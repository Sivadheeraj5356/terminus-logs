FROM public.ecr.aws/docker/library/gcc:13-bookworm@sha256:930f2ebe239275fa67226654cb79273ea34eee672ae61c8a39f689c37fb7ac5c

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    asciinema=2.2.0-1 \
    bash=5.2.15-2+b10 \
    ca-certificates=20230311+deb12u1 \
    cmake=3.25.1-1 \
    curl=7.88.1-10+deb12u14 \
    make=4.3-4.1 \
    patch=2.7.6-7 \
    python3=3.11.2-1+b1 \
    python3-pip=23.0.1+dfsg-1 \
    tmux=3.3a-3 \
  && rm -rf /var/lib/apt/lists/* \
  && tmux -V \
  && asciinema --version

RUN python3 -m pip install --no-cache-dir --break-system-packages \
    pytest==8.4.1 \
    pytest-json-ctrf==0.3.5

ARG RUST_TOOLCHAIN=1.85.0
RUN curl -fsSL https://sh.rustup.rs | sh -s -- -y --no-modify-path --profile minimal --default-toolchain "${RUST_TOOLCHAIN}" \
  && /root/.cargo/bin/rustc --version

ENV PATH="/root/.cargo/bin:${PATH}"

RUN mkdir -p /app/tmp /app/output /app/build /logs/verifier /logs/agent \
    && chmod 1777 /app/tmp \
    && rm -rf /tmp/tmux-0 /tmp/tmux-* /app/tmux /logs/agent/tmux 2>/dev/null || true

ENV TMPDIR=/app/tmp \
    TMUX_TMPDIR=/dev/shm/terminus-tmux \
    BASH_ENV=/etc/terminus-tmux-init.sh

WORKDIR /app

COPY . /app/environment

RUN chmod 755 /app/environment/etc/terminus-tmux-init.sh \
    && install -m 0755 /app/environment/etc/terminus-tmux-init.sh /etc/terminus-tmux-init.sh \
    && install -m 0644 /app/environment/etc/profile.d/99-terminus-session.sh \
        /etc/profile.d/99-terminus-session.sh \
    && grep -q terminus-tmux-init /etc/bash.bashrc \
       || echo '. /etc/terminus-tmux-init.sh' >> /etc/bash.bashrc
