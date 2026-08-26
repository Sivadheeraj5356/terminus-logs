# Go build environment + verifier Python stack for tests/test.sh.
# Final stage keeps the Go toolchain because agents must compile at runtime.

FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac

ENV DEBIAN_FRONTEND=noninteractive
ENV GOTOOLCHAIN=local
ENV GO111MODULE=on
ENV CGO_ENABLED=0
# Keep Go on PATH for both non-login and login shells (bash -lc resets PATH via /etc/profile).
ENV PATH=/usr/local/go/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        ca-certificates=20230311+deb12u1 \
        make=4.3-4.1 \
        tmux=3.3a-3 \
        asciinema \
        python3 \
        python3-pip \
 && python3 -m pip install --no-cache-dir --break-system-packages \
        pytest==8.4.1 \
        pytest-json-ctrf==0.3.5 \
        pyyaml==6.0.2 \
 && printf '%s\n' 'export PATH="/usr/local/go/bin:${PATH}"' > /etc/profile.d/golang-path.sh \
 && chmod 644 /etc/profile.d/golang-path.sh \
 && ln -sf /usr/local/go/bin/go /usr/local/bin/go \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY go.mod /app/
RUN go mod download

COPY Makefile /app/
COPY contracts/OUTPUT_SCHEMA.md /app/contracts/OUTPUT_SCHEMA.md
COPY references/session_format.md /app/references/session_format.md
COPY policy/equivalence_rules.yaml /app/policy/equivalence_rules.yaml
COPY toolchain-cli /app/toolchain-cli
COPY artifact-registry /app/artifact-registry
COPY pipeline-runner /app/pipeline-runner
COPY report-writer /app/report-writer
COPY equivalence-engine /app/equivalence-engine
COPY build-sessions /app/build-sessions

RUN mkdir -p /app/bin /app/output
