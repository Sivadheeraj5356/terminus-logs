FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        asciinema=2.2.0-1 \
        ca-certificates=20230311+deb12u1 \
        patch=2.7.6-7 \
        python3=3.11.2-1+b1 \
        python3-pip=23.0.1+dfsg-1 \
        tmux=3.3a-3 \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /app/bin /app/output /app/state

COPY requirements.lock /tmp/requirements.lock
RUN pip3 install --no-cache-dir --break-system-packages \
    --require-hashes -r /tmp/requirements.lock \
    && rm /tmp/requirements.lock

WORKDIR /app

COPY go.mod go.sum /app/environment/
COPY cmd/ /app/environment/cmd/
COPY k3c/ /app/environment/k3c/
COPY m9f/ /app/environment/m9f/
COPY r6s/ /app/environment/r6s/
COPY pkg/ /app/environment/pkg/
COPY scripts/ /app/environment/scripts/
COPY migrations/ /app/environment/migrations/
COPY fixtures/ /app/environment/fixtures/
COPY docs/ /app/environment/docs/
COPY p3/ /app/environment/p3/
COPY m4/ /app/environment/m4/
COPY c44.txt /app/environment/c44.txt

RUN chmod +x /app/environment/scripts/*.sh /app/environment/migrations/cln8.sh \
    && /app/environment/scripts/rebuild_bins.sh

ENV PATH="/app/bin:${PATH}"
