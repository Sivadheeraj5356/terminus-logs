# Builder stage: compiles the probe reference binary. Only the stripped
# binary reaches the runtime image; its source never does.
FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac AS refbuild
ENV CGO_ENABLED=0 GOTOOLCHAIN=local GOPROXY=off GOSUMDB=off GOCACHE=/tmp/gocache
COPY ref/ /refsrc/
RUN cd /refsrc && go build -trimpath -ldflags="-s -w" -o /ref .

# Canonical Go base image (covers Go 1.21-1.26). The agent writes and compiles a
# Go program, so the Go toolchain is the required runtime. python3 is present
# only to run the offline pytest verifier. Digest matches the canonical Go entry
# on the approved base-image list.
FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac

ENV DEBIAN_FRONTEND=noninteractive

# Wire the Go toolchain onto every shell's PATH. The base image only exports it
# via ENV PATH, which a login shell (the agent's interactive tmux shell) resets;
# the symlinks under /usr/local/bin and the profile.d entry keep `go` reachable
# for the agent as well as the verifier and oracle.
ENV GOROOT=/usr/local/go
ENV PATH=/usr/local/go/bin:/usr/local/bin:/usr/bin:/bin:${PATH}
RUN ln -sf /usr/local/go/bin/go /usr/local/bin/go \
    && ln -sf /usr/local/go/bin/gofmt /usr/local/bin/gofmt \
    && printf 'export GOROOT=/usr/local/go\nexport PATH=/usr/local/go/bin:$PATH\n' > /etc/profile.d/golang.sh \
    && chmod +x /etc/profile.d/golang.sh \
    && printf '\nexport GOROOT=/usr/local/go\nexport PATH=/usr/local/go/bin:$PATH\n' >> /root/.bashrc

# Agent runtime (tmux, asciinema) plus a Python interpreter for the verifier.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        asciinema \
        binutils \
        ca-certificates \
        file \
        python3 \
        python3-pip \
        tmux \
    && rm -rf /var/lib/apt/lists/*

# Pinned Python packages for the verifier, installed at build time (offline run).
COPY app/requirements.txt /tmp/requirements.txt
RUN pip3 install --no-cache-dir --break-system-packages --require-hashes --no-deps \
    -r /tmp/requirements.txt

# Offline Go: pin the toolchain (no version fetch), disable the module proxy and
# checksum DB, and warm a world-writable build cache so the agent can compile as
# any user with no network. The deliverable is standard-library only, so no
# module downloads are required.
ENV GOTOOLCHAIN=local \
    GOPROXY=off \
    GOSUMDB=off \
    GOFLAGS=-mod=mod \
    CGO_ENABLED=0 \
    GOPATH=/go \
    GOCACHE=/go/cache \
    GOMODCACHE=/go/pkg/mod
RUN mkdir -p /go/cache /go/pkg/mod /warm \
    && printf 'module warm\n\ngo 1.24\n' > /warm/go.mod \
    && printf 'package main\n\nimport (\n\t"bufio"\n\t"fmt"\n\t"math"\n\t"os"\n\t"sort"\n\t"strconv"\n\t"strings"\n)\n\nfunc main() {\n\t_ = fmt.Sprint(math.Log(2), bufio.NewReader(os.Stdin), sort.Ints, strconv.Itoa, strings.TrimSpace)\n}\n' > /warm/main.go \
    && (cd /warm && go build -o /tmp/warm . ) \
    && rm -rf /tmp/warm /warm \
    && chmod -R a+rwX /go

WORKDIR /app

COPY app/data/ ./data/
COPY app/docs/ ./docs/
COPY --from=refbuild --chmod=0755 /ref /app/ref

RUN mkdir -p /app/output
