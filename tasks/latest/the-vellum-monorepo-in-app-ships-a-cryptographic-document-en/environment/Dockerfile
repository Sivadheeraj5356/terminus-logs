FROM public.ecr.aws/docker/library/rust:1.85-slim@sha256:9f841bbe9e7d8e37ceb96ed907265a3a0df7f44e3737d0b100e7907a679acb36

ENV DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    TZ=UTC \
    CARGO_NET_OFFLINE=true \
    CARGO_HOME=/usr/local/cargo \
    RUSTUP_HOME=/usr/local/rustup \
    PATH=/usr/local/cargo/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tmux=3.3a-3 \
        asciinema=2.2.0-1 \
        python3=3.11.2-1+b1 \
        python3-pip=23.0.1+dfsg-1 \
        python3-venv=3.11.2-1+b1 \
        nodejs=18.20.4+dfsg-1~deb12u2 \
        npm=9.2.0~ds1-1 \
        openssl=3.0.20-1~deb12u2 \
        patchelf=0.14.3-1+b1 \
        binutils=2.40-2 \
        file=1:5.44-3 \
        jq=1.6-2.1+deb12u2 \
        xz-utils=5.4.1-1+deb12u1 \
        zip=3.0-13 \
        unzip=6.0-28 \
        make=4.3-4.1 \
        gcc=4:12.2.0-3 \
        pkg-config=1.8.1-1 \
        ca-certificates=20230311+deb12u1 \
    && rm -rf /var/lib/apt/lists/*

RUN ln -sf /usr/bin/python3 /usr/local/bin/python

COPY requirements-verifier.txt /tmp/requirements-verifier.txt
RUN pip3 install --no-cache-dir --break-system-packages -r /tmp/requirements-verifier.txt

COPY app /app

RUN /app/scripts/dev-build \
    && chmod -R a+rwX /usr/local/cargo \
    && mkdir -p /output \
    && chmod -R a+rwX /output /app
