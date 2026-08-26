FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac

ENV PATH=/usr/local/go/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
ENV PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    CGO_ENABLED=0 \
    GOTOOLCHAIN=local \
    GOPROXY=off

WORKDIR /app

RUN apt-get update \
 && apt-get install -y --no-install-recommends python3 python3-pip ca-certificates tmux asciinema \
 && rm -rf /var/lib/apt/lists/* \
 && pip3 install --no-cache-dir --break-system-packages pytest==8.4.1 pytest-json-ctrf==0.3.5 \
 && ln -sf /usr/local/go/bin/go /usr/local/bin/go \
 && ln -sf /usr/local/go/bin/gofmt /usr/local/bin/gofmt \
 && printf 'export PATH=/usr/local/go/bin:$PATH\n' > /etc/profile.d/go.sh \
 && printf '\nexport PATH=/usr/local/go/bin:$PATH\n' >> /etc/bash.bashrc \
 && go version

COPY keyshare_engine /app/keyshare_engine
COPY service_inventory /app/data/service_inventory
COPY group_catalog /app/data/group_catalog
COPY rollout_schedule /app/data/rollout_schedule
COPY admission_policy /app/data/admission_policy
COPY quota_ledger /app/data/quota_ledger
COPY pin_seals /app/data/pin_seals
COPY tenant_overlay /app/data/tenant_overlay
COPY handshake_capture /app/data/handshake_capture

RUN mkdir -p /app/bin /app/output \
 && cd /app/keyshare_engine \
 && go build -o /app/bin/keyshare_witness . \
 && go clean -cache -modcache -testcache 2>/dev/null || true

CMD ["/bin/bash"]
