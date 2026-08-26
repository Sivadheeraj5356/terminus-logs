FROM public.ecr.aws/docker/library/rust:1.85-slim@sha256:9f841bbe9e7d8e37ceb96ed907265a3a0df7f44e3737d0b100e7907a679acb36

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
        asciinema \
        ca-certificates \
        pkg-config \
        postgresql-15 \
        postgresql-contrib-15 \
        procps \
        python3 \
        python3-pip \
        tmux \
        tzdata \
    && rm -rf /var/lib/apt/lists/*

RUN pip3 install --break-system-packages --no-cache-dir \
        pytest==8.3.4 \
        psycopg2-binary==2.9.10

# The cluster postinst is not deterministic across builds, so create it only if the
# package did not. Loopback trust auth: the same DSN serves the service and the tests.
RUN { [ -d /etc/postgresql/15/main ] || pg_createcluster 15 main ; } \
    && printf 'local all all trust\nhost all all 127.0.0.1/32 trust\nhost all all ::1/128 trust\n' \
        > /etc/postgresql/15/main/pg_hba.conf \
    && printf "listen_addresses='127.0.0.1'\n" >> /etc/postgresql/15/main/postgresql.conf \
    && pg_ctlcluster 15 main start \
    && su postgres -c "psql -q -c \"CREATE ROLE tzforge LOGIN SUPERUSER\"" \
    && su postgres -c "createdb -O tzforge tzforge" \
    && pg_ctlcluster 15 main stop

WORKDIR /app
COPY app/ /app/
RUN cargo build --release --locked

# Crates are vendored in the image; nothing reaches the network after this point.
ENV CARGO_NET_OFFLINE=true

COPY config/ /app/config/
COPY data/ /app/data/
COPY docs/ /app/docs/
COPY bin/ /app/bin/
