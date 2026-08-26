FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac

# restcountries-payroll single-step environment
# build-id: 6 (added the global social-contribution ceiling: largest-remainder
# apportionment across the report run + reverse two-leg pivot conversion,
# genuine coupling trap on top of the existing floor/cap and tie-break levers)
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=UTC
ENV PATH=/usr/local/go/bin:/go/bin:${PATH}
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-pip ca-certificates tmux asciinema=2.2.0-1 sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# Verifier dependencies are hash-locked (pytest + pytest-json-ctrf and their
# full transitive closure) via --require-hashes.
COPY requirements.lock /tmp/requirements.lock
RUN python3 -m pip install --no-cache-dir --break-system-packages \
    --require-hashes -r /tmp/requirements.lock

# Keep go reachable even under a bare login shell that resets PATH.
RUN ln -sf /usr/local/go/bin/go /usr/local/bin/go

COPY crosspay-app /app

RUN chmod +x /app/scripts/*.sh 2>/dev/null || true

ENV GOFLAGS=-mod=mod
ENV GOTOOLCHAIN=local

# cache-bust 20260720T220500Z_v13_global_social_cap
