# syntax=docker/dockerfile:1
FROM public.ecr.aws/docker/library/python:3.13-slim-bookworm@sha256:01f42367a0a94ad4bc17111776fd66e3500c1d87c15bbd6055b7371d39c124fb

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends asciinema=2.2.0-1 ca-certificates=20230311+deb12u1 nodejs=18.20.4+dfsg-1~deb12u2 npm=9.2.0~ds1-1 php-cli=2:8.2+93 php-sqlite3=2:8.2+93 sqlite3=3.40.1-2+deb12u2 tmux=3.3a-3 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /tmp/requirements.txt
RUN python3 -m venv /opt/verifier \
    && /opt/verifier/bin/pip install --no-cache-dir --require-hashes --no-deps -r /tmp/requirements.txt
RUN rm -f /tmp/requirements.txt

ENV PATH=/opt/verifier/bin:${PATH}

# Verifier pytest tooling is baked here for allow_internet=false; the verifier must not pip install at runtime.

COPY package.json package-lock.json /app/
RUN npm ci --omit=dev

COPY booth/ /app/booth/
COPY config/ /app/config/
COPY data/ /app/data/
COPY docs/ /app/docs/
COPY fixtures/ /app/fixtures/
COPY harness/ /app/harness/
COPY lib/ /app/lib/
COPY mod-h7/ /app/mod-h7/
COPY mod-k9/ /app/mod-k9/
COPY mod-m3/ /app/mod-m3/
COPY mod-n4/ /app/mod-n4/
COPY mod-p2/ /app/mod-p2/
COPY mod-q1/ /app/mod-q1/
COPY mod-r8/ /app/mod-r8/
COPY mod-s2/ /app/mod-s2/
COPY lanes/ /app/lanes/
COPY desk_contracts/ /app/desk_contracts/
COPY profiles/ /app/profiles/
COPY scripts/ /app/scripts/
COPY svc/ /app/svc/

RUN chmod +x /app/scripts/*.sh /app/lanes/*.sh /app/desk_contracts/*.sh \
    && bash /app/scripts/build_all.sh \
    && mkdir -p /app/run /app/output /opt/verifier-fixtures

COPY verifier-fixtures/ /opt/verifier-fixtures/
