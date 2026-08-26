FROM public.ecr.aws/docker/library/eclipse-temurin:21-jdk-jammy@sha256:25d1276565738d3c805e632a4542c3a7598866ef967f4def6544c15de3a74b14

LABEL org.opencontainers.image.title="relicmaze-postgres-jdbc-resolver"
LABEL org.opencontainers.image.description="RelicMaze game-master resolver over PostgreSQL/JDBC"
LABEL org.opencontainers.image.licenses="Apache-2.0"

ENV DEBIAN_FRONTEND=noninteractive

# OS packages: PostgreSQL (DB engine), Node.js/npm (verifier), Python (test
# harness), plus the harness session tools. Verifier needs no network at
# runtime, so everything is installed here at build time.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        asciinema \
        ca-certificates \
        curl \
        nodejs \
        npm \
        postgresql \
        postgresql-contrib \
        python3 \
        python3-pip \
        tmux \
    && rm -rf /var/lib/apt/lists/* \
    && if [ ! -e /usr/bin/node ] && [ -e /usr/bin/nodejs ]; then ln -s /usr/bin/nodejs /usr/bin/node; fi

# Pinned Python test dependencies (baked in; not installed at runtime).
RUN pip3 install --no-cache-dir \
        pytest==8.4.1 \
        pytest-json-ctrf==0.3.5

# Starter library and helper scripts.
COPY app/ /app/
COPY scripts/ensure-db.sh /usr/local/bin/relicmaze-ensure-db.sh
COPY scripts/boot.sh /usr/local/bin/relicmaze-boot.sh
RUN chmod 0755 /usr/local/bin/relicmaze-ensure-db.sh /usr/local/bin/relicmaze-boot.sh /app/relicmaze/build.sh

# Java dependencies: PostgreSQL JDBC driver and org.json, pinned by version and
# verified by SHA-256 (downloaded at build time only).
RUN mkdir -p /app/relicmaze/lib \
    && curl -fsSL -o /app/relicmaze/lib/postgresql.jar \
        https://repo1.maven.org/maven2/org/postgresql/postgresql/42.7.4/postgresql-42.7.4.jar \
    && echo "188976721ead8e8627eb6d8389d500dccc0c9bebd885268a3047180274a6031e  /app/relicmaze/lib/postgresql.jar" | sha256sum -c - \
    && curl -fsSL -o /app/relicmaze/lib/json.jar \
        https://repo1.maven.org/maven2/org/json/json/20240303/json-20240303.jar \
    && echo "3cf6cd6892e32e2b4c1c39e0f52f5248a2f5b37646fdfbb79a66b46b618414ed  /app/relicmaze/lib/json.jar" | sha256sum -c -

# Load the authoritative dataset into the cluster and then delete the seed
# file, so the data is only reachable through the running database.
COPY db/seed.sql /tmp/seed.sql
RUN set -eux; \
    PG_VER="$(ls /etc/postgresql)"; \
    printf 'listen_addresses = %s\nport = 5432\n' "'localhost'" >> "/etc/postgresql/$PG_VER/main/postgresql.conf"; \
    printf 'local all all trust\nhost all all 127.0.0.1/32 trust\nhost all all ::1/128 trust\n' > "/etc/postgresql/$PG_VER/main/pg_hba.conf"; \
    pg_ctlcluster "$PG_VER" main start; \
    for _ in $(seq 1 60); do pg_isready -q -h localhost && break; sleep 0.5; done; \
    su postgres -c "psql -v ON_ERROR_STOP=1 -c \"CREATE ROLE relickeeper LOGIN PASSWORD 'relickeeper';\""; \
    su postgres -c "createdb -O relickeeper relicmaze"; \
    psql -h localhost -U relickeeper -d relicmaze -v ON_ERROR_STOP=1 -f /tmp/seed.sql; \
    pg_ctlcluster "$PG_VER" main stop; \
    rm -f /tmp/seed.sql

WORKDIR /app

ENTRYPOINT ["/usr/local/bin/relicmaze-boot.sh"]
CMD ["sleep", "infinity"]
