FROM public.ecr.aws/docker/library/python:3.13-slim-bookworm@sha256:01f42367a0a94ad4bc17111776fd66e3500c1d87c15bbd6055b7371d39c124fb

WORKDIR /app

# tmux + asciinema are required by the terminus-2 harness. Everything else is
# what the task itself needs: the PHP toolchain the provisioning tool is
# written against, the Redis server holding the link ledger registry, and
# composer for the Slim API.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tmux=3.3a-* \
        asciinema=2.2.0-* \
        curl=7.88.1-* \
        ca-certificates=20230311* \
        unzip=6.0-* \
        procps=2:4.0.2-* \
        redis-server=5:7.0.* \
        redis-tools=5:7.0.* \
        php-cli=2:8.2+* \
        php-mbstring=2:8.2+* \
        php-curl=2:8.2+* \
        php-xml=2:8.2+* \
        php-gmp=2:8.2+* \
        composer=2.5.* \
    && rm -rf /var/lib/apt/lists/*

# Verifier toolchain, baked at build time because the task runs offline.
RUN python -m pip install --no-cache-dir \
    pytest==8.4.1 \
    pytest-json-ctrf==0.3.5

COPY app/ /app/

RUN chmod +x /app/scripts/start-services.sh \
    && mkdir -p /app/out /app/bin /var/log/linkreg-api /var/lib/redis \
        /etc/systemd/network /etc/link-rate.d /var/lib/link-rate

# Slim + predis for the link registry API, installed from the committed
# composer.lock so the dependency tree is byte-identical on every build. The
# container never reaches the network again.
RUN cd /app/api \
    && COMPOSER_ALLOW_SUPERUSER=1 composer install --no-interaction --no-dev --prefer-dist --no-progress \
    && composer clear-cache

# Generate the ledger records and the private metadata the API serves, then
# load the records into Redis and persist the snapshot. The fixture
# self-asserts inside gen_data.py fail the build if any stated rule stops
# firing in the data.
COPY build/redis-linkreg.conf /etc/redis/linkreg.conf
COPY build/gen_data.py /tmp/build/gen_data.py
RUN set -eu; \
    python /tmp/build/gen_data.py; \
    redis-server /etc/redis/linkreg.conf; \
    for _ in $(seq 1 60); do redis-cli ping >/dev/null 2>&1 && break; sleep 0.25; done; \
    redis-cli --pipe < /tmp/build/seed.resp; \
    redis-cli save; \
    redis-cli shutdown nosave || true; \
    sleep 1; \
    test -s /var/lib/redis/dump.rdb; \
    rm -rf /tmp/build /root/.composer /root/.cache

CMD ["/bin/bash", "-c", "/app/scripts/start-services.sh >/dev/null 2>&1 || true; sleep infinity"]
