FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac

RUN apt-get update && apt-get install -y --no-install-recommends \
        make \
        ca-certificates \
        python3 \
        python3-pip \
        tmux \
        asciinema \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --break-system-packages --no-cache-dir pytest==8.4.1 pytest-json-ctrf==0.3.5

ENV PATH=/usr/local/go/bin:/go/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
ENV GOPROXY=off
ENV GOSUMDB=off
ENV GOTOOLCHAIN=local
ENV GOCACHE=/opt/go-cache

RUN ln -sf /usr/local/go/bin/go /usr/bin/go && ln -sf /usr/local/go/bin/gofmt /usr/bin/gofmt

RUN printf 'export PATH=/usr/local/go/bin:/go/bin:$PATH\nexport GOPROXY=off\nexport GOSUMDB=off\nexport GOTOOLCHAIN=local\nexport GOCACHE=/opt/go-cache\n' > /etc/profile.d/go.sh && chmod +x /etc/profile.d/go.sh

RUN printf 'command -v go >/dev/null 2>&1 || export PATH=/usr/local/go/bin:/go/bin:$PATH\n' >> /etc/bash.bashrc

COPY app/ /app/

WORKDIR /app

RUN cd /app && go vet ./... && make build
