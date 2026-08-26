FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac
RUN apt-get update && apt-get install -y --no-install-recommends bash ca-certificates git tmux asciinema make python3 python3-pytest && rm -rf /var/lib/apt/lists/*
ENV GOTOOLCHAIN=auto
WORKDIR /app/repo
COPY repo/ /app/repo/
RUN git init -q && git add -A && git -c user.email=task@example.invalid -c user.name=task commit -qm initial
RUN ln -sf /usr/local/go/bin/go /usr/local/bin/go && mkdir -p /app/repo/bin && go build -o /app/repo/bin/trace_blur ./cmd/trace_blur
