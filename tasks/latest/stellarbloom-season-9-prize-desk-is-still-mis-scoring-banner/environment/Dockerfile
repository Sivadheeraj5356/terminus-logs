FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac

ENV PATH="/usr/local/go/bin:/go/bin:${PATH}"

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        python3 \
        python3-pip \
        tmux \
        asciinema \
    && rm -rf /var/lib/apt/lists/* \
    && echo 'export PATH="/usr/local/go/bin:/go/bin:$PATH"' >> /root/.bashrc \
    && printf '%s\n' 'export PATH="/usr/local/go/bin:/go/bin:$PATH"' > /etc/profile.d/go-path.sh

RUN pip3 install --break-system-packages --no-cache-dir \
    pytest==8.4.1 \
    pytest-json-ctrf==0.3.5

WORKDIR /app

COPY go.mod go.sum /app/
RUN go mod download

COPY cmd/ /app/cmd/
COPY pkg/ /app/pkg/
COPY internal/ /app/internal/
COPY config/ /app/config/
COPY data/ /app/data/
COPY docs/ /app/docs/
COPY scripts/ /app/scripts/
COPY benchmarks/ /app/benchmarks/

RUN mkdir -p /app/bin /app/output \
    && chmod +x /app/scripts/run_audit.sh /app/benchmarks/run_benchmark.sh \
    && go build -o /app/bin/gachaudit ./cmd/gachaudit

WORKDIR /app
