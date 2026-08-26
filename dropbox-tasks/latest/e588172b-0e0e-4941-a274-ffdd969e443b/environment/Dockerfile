FROM debian:bookworm-slim@sha256:4724b8cc51e33e398f0e2e15e18d5ec2851ff0c2280647e1310bc1642182655d

WORKDIR /app

# Host schedule rebuild helpers need a C toolchain at runtime so operators can
# recompile after policy edits; keep single-stage (agent rebuilds after fixes).
COPY requirements.txt /tmp/requirements.txt

RUN apt-get update && apt-get install -y --no-install-recommends \
        bash=5.2.15-2+b13 \
        coreutils=9.1-1 \
        gcc=4:12.2.0-3 \
        make=4.3-4.1 \
        libc6-dev=2.36-9+deb12u14 \
        libssl-dev=3.0.20-1~deb12u2 \
        openssl=3.0.20-1~deb12u2 \
        ca-certificates=20230311+deb12u1 \
        tmux=3.3a-3 \
        asciinema=2.2.0-1 \
        python3=3.11.2-1+b1 \
        python3-pip=23.0.1+dfsg-1 \
    && rm -rf /var/lib/apt/lists/*

# Offline verifier deps: pytest==8.4.1 pytest-json-ctrf==0.3.5
RUN python3 -m pip install --no-cache-dir --break-system-packages \
    --require-hashes --no-deps -r /tmp/requirements.txt

COPY Makefile /app/environment/Makefile
COPY docs /app/environment/docs
COPY data /app/environment/data
COPY tools /app/environment/tools
COPY m5s /app/environment/m5s
COPY n2h /app/environment/n2h
COPY u4r /app/environment/u4r
COPY q8k /app/environment/q8k
COPY rowpack /app/environment/rowpack
COPY src /app/environment/src

RUN make -C /app/environment clean all \
    && mkdir -p /app/tools /app/output /app/output/step \
    && ln -sf /app/environment/data /app/data \
    && cp /app/environment/build/step_tool /app/tools/step_tool \
    && cp /app/environment/build/pack_tool /app/tools/pack_tool \
    && chmod +x /app/tools/step_tool /app/tools/pack_tool

ENV PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

CMD ["sh", "-c", "echo Environment ready"]
