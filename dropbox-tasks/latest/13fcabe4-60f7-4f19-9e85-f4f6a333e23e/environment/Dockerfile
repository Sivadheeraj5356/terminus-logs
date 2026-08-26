FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac

RUN apt-get update && apt-get install -y --no-install-recommends \
    bind9=1:9.18.49-1~deb12u1 \
    bind9utils=1:9.18.49-1~deb12u1 \
    dnsutils=1:9.18.49-1~deb12u1 \
    jq=1.6-2.1+deb12u2 \
    make=4.3-4.1 \
    git=1:2.39.5-0+deb12u3 \
    tmux=3.3a-3 \
    asciinema=2.2.0-1 \
    patch=2.7.6-7 \
    ca-certificates=20230311+deb12u1 \
    python3=3.11.2-1+b1 \
    python3-pip=23.0.1+dfsg-1 \
    python3-venv=3.11.2-1+b1 \
    util-linux=2.38.1-5+deb12u3 \
    && rm -rf /var/lib/apt/lists/*

COPY bind-signzone-wrap.sh /usr/local/bin/bind-signzone-wrap.sh
RUN chmod +x /usr/local/bin/bind-signzone-wrap.sh \
    && mv /usr/bin/dnssec-signzone /usr/bin/dnssec-signzone.real \
    && ln -sf /usr/local/bin/bind-signzone-wrap.sh /usr/bin/dnssec-signzone \
    && ln -sf /usr/bin/dnssec-signzone /usr/local/bin/dnssec-signzone

COPY vendor/pip-wheels/ /tmp/pip-wheels/
RUN python3 -m venv /opt/verifier-venv \
    && /opt/verifier-venv/bin/pip install --no-index --find-links=/tmp/pip-wheels \
        pytest==8.4.1 \
        pytest-json-ctrf==0.3.5
RUN rm -rf /tmp/pip-wheels

WORKDIR /app
COPY app/ /app/
COPY data/ /data/
COPY go-vendor.tar.gz /tmp/go-vendor.tar.gz
COPY build-visible-fixtures.sh /build-visible-fixtures.sh

RUN tar -xzf /tmp/go-vendor.tar.gz -C /app \
    && rm -f /tmp/go-vendor.tar.gz \
    && chmod +x /build-visible-fixtures.sh /app/scripts/*.sh \
    && bash /build-visible-fixtures.sh \
    && chown -R root:root /data && chmod -R a-w /data \
    && mkdir -p /work /output /logs/verifier /logs/agent \
    && make -C /app build

ENV PATH="/usr/local/go/bin:/opt/verifier-venv/bin:${PATH}" \
    WORKSPACE_DIR=/work \
    TZ=UTC \
    LC_ALL=C.UTF-8 \
    LANG=C.UTF-8 \
    GOPROXY=off

CMD ["sleep", "infinity"]
