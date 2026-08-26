FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac

ENV PATH="/usr/local/go/bin:${PATH}"

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-pip tmux asciinema && rm -rf /var/lib/apt/lists/*

RUN pip install --break-system-packages pytest==8.4.1 pytest-json-ctrf==0.3.5

WORKDIR /app

COPY go.mod /app/
RUN mkdir -p cmd/raman-temp && \
    echo 'package main\nfunc main(){}' > cmd/raman-temp/main.go && \
    go mod tidy && go build -o /tmp/bootstrap ./cmd/raman-temp

COPY cmd/ /app/cmd/
COPY pkg/ /app/pkg/
COPY config/ /app/config/
COPY data/ /app/data/
COPY docs/ /app/docs/

RUN go build -o /app/bin/raman-temp ./cmd/raman-temp

RUN mkdir -p /app/output

RUN echo 'export PATH="/usr/local/go/bin:$PATH"' >> /root/.bashrc
