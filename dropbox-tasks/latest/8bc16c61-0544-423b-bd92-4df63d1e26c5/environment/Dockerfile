FROM public.ecr.aws/docker/library/rust:1.85-slim@sha256:9f841bbe9e7d8e37ceb96ed907265a3a0df7f44e3737d0b100e7907a679acb36

ENV PATH="/usr/local/cargo/bin:${PATH}"

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        asciinema \
        python3 \
        python3-pip \
        python-is-python3 \
        tmux \
    && rm -rf /var/lib/apt/lists/*

RUN rustup target add wasm32-wasip2

RUN ln -sf /usr/local/cargo/bin/cargo /usr/local/bin/cargo \
    && ln -sf /usr/local/cargo/bin/rustc /usr/local/bin/rustc \
    && ln -sf /usr/local/cargo/bin/rustup /usr/local/bin/rustup

RUN python3 -m pip install --break-system-packages --no-cache-dir \
    pytest==8.4.1 \
    pytest-json-ctrf==0.3.5

WORKDIR /app

COPY . /app/
RUN chmod 0755 /app/tools/build-component.sh /app/tools/run-faults.sh /app/tools/run-fixed.sh
