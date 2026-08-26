FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac

WORKDIR /app

# Agent session setup runs `tmux -V` and `asciinema --version`. Preinstall both on
# custom bases so runtime apt is skipped when allow_internet=false.
RUN DEBIAN_FRONTEND=noninteractive apt-get update \
  && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    bash=5.2.15-2+b13 \
    coreutils=9.1-1 \
    ca-certificates=20230311+deb12u1 \
    python3=3.11.2-1+b1 \
    python3-pip=23.0.1+dfsg-1 \
    tmux=3.3a-3 \
    asciinema=2.2.0-1 \
  && rm -rf /var/lib/apt/lists/* \
  && command -v tmux >/dev/null \
  && command -v asciinema >/dev/null \
  && command -v sha256sum >/dev/null \
  && tmux -V \
  && asciinema --version

COPY . /app/environment

# Verifier-only Python deps (pinned). Installed at build time because allow_internet=false;
# tests/test.sh must not download packages. Pins live in environment/verifier-requirements.txt.
RUN python3 -m pip install --break-system-packages --no-cache-dir \
    -r /app/environment/verifier-requirements.txt

RUN mkdir -p /app/bin /app/output \
  && chmod +x /app/environment/tools/runner.sh \
  && cd /app/environment && go mod download \
  && go build -trimpath -ldflags="-s -w" -o /app/bin/dschedsim ./cmd/dschedsim \
  && go build -trimpath -ldflags="-s -w" -o /app/bin/sched_probe ./cmd/sched_probe

# Re-install and verify session tools in the final image layer so agent setup
# can probe tmux/asciinema without runtime apt when allow_internet=false.
RUN DEBIAN_FRONTEND=noninteractive apt-get update \
  && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    tmux=3.3a-3 \
    asciinema=2.2.0-1 \
  && rm -rf /var/lib/apt/lists/* \
  && python3 -m pytest --version \
  && command -v tmux >/dev/null \
  && command -v asciinema >/dev/null \
  && command -v sha256sum >/dev/null \
  && tmux -V \
  && asciinema --version \
  && test -x /app/bin/dschedsim
