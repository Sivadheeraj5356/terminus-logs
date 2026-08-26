# Runtime: golang:1.24-bookworm is a sanctioned base (check_sanctioned_base_images).
# The task ships a package registry and a fixed Go consumer; the agent writes its
# own resolver plus a Go compat package and must build the project for real, so
# the Go toolchain lives in the runtime stage where the agent works. Python and
# pytest are added for the verifier only. allow_internet=false at runtime, so
# every verifier dependency is baked here at build time.
FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac

# Harness tooling + the Python verifier runtime.
#   ca-certificates    - base hygiene for tmux/asciinema
#   tmux, asciinema    - the harbor harness records the agent session
#   python3, pip       - the verifier is pytest-based
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        tmux \
        asciinema \
        python3 \
        python3-pip \
    && rm -rf /var/lib/apt/lists/*

# Verifier deps. test.sh cannot install at runtime because allow_internet=false,
# so pytest and the ctrf plugin are baked here. bookworm's python3 is
# externally-managed, hence --break-system-packages for this isolated image.
RUN python3 -m pip install --no-cache-dir --break-system-packages \
        pytest==8.4.1 \
        pytest-json-ctrf==0.3.5

# Every build in this task, oracle or agent, only ever touches the standard
# library plus the registry stubs and the compat package written locally, so
# GOTOOLCHAIN=local keeps go from trying to fetch anything under
# allow_internet=false.
ENV GOCACHE=/root/.cache/go-build \
    CGO_ENABLED=0 \
    GOTOOLCHAIN=local \
    GOPROXY=off \
    GOFLAGS=-mod=mod \
    PATH="/usr/local/go/bin:${PATH}"

WORKDIR /app

COPY README.md RULES.md manifest.toml ./
COPY docs/ ./docs/
COPY registry/ ./registry/
COPY project/ ./project/

CMD ["bash"]
