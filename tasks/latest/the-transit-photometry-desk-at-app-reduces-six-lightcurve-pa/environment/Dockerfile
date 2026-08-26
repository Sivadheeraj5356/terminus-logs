# Offline Go transit desk. Builder: golang:1.24-bookworm. Runtime: python:3.13-slim-bookworm.
# Avoid COPY --chmod/--chown (requires BuildKit); use plain COPY + chmod/chown.
FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac AS gobuilder

WORKDIR /src
COPY go.mod ./
COPY phase ./phase
COPY zknot ./zknot
COPY xvox ./xvox
COPY knotr ./knotr
COPY kernel ./kernel
COPY desk ./desk
COPY desk_bin ./desk_bin
COPY legacy_bin ./legacy_bin
RUN go build -o /tmp/desk ./desk_bin && go build -o /tmp/legacy ./legacy_bin

FROM public.ecr.aws/docker/library/python:3.13-slim-bookworm@sha256:01f42367a0a94ad4bc17111776fd66e3500c1d87c15bbd6055b7371d39c124fb

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        asciinema=2.2.0-1 \
        ca-certificates=20230311+deb12u1 \
        libevent-core-2.1-7=2.1.12-stable-8 \
        libutempter0=1.2.1-3 \
        tmux=3.3a-3 \
    && apt-mark manual tmux asciinema libevent-core-2.1-7 libutempter0 \
    && rm -rf /var/lib/apt/lists/* \
    && install -d -m 1777 /tmp \
    && install -d -m 0777 /tmp/.config /tmp/.config/asciinema \
    && install -d -m 0755 /opt/verifier \
    && install -d -m 1777 /logs /logs/verifier \
    && install -d -m 0777 /app/output /app/work /app/legacy /app/bin \
    && install -d -m 0775 \
        /home/model \
        /home/model/.cache \
        /home/model/.cache/go-build \
        /home/model/go \
        /home/model/go/pkg/mod

COPY verifier-requirements.txt /opt/verifier-requirements.txt
RUN python3 -m pip install --no-cache-dir --break-system-packages \
        --require-hashes \
        -r /opt/verifier-requirements.txt

RUN rm -rf /root/.cache/pip \
    && ln -sf /usr/local/bin/python3.13 /usr/bin/python3 \
    && ln -sf /usr/local/bin/python3.13 /usr/bin/python \
    && ln -sf /usr/local/bin/asciinema /usr/bin/asciinema \
    && python3 -m pytest --version \
    && test -x /usr/bin/tmux \
    && test -x /usr/bin/asciinema \
    && chmod 0444 /opt/verifier-requirements.txt

# Toolchain for offline rebuilds; drop docs/tests to keep the image lean for Daytona.
COPY --from=gobuilder /usr/local/go /usr/local/go
RUN rm -rf /usr/local/go/test /usr/local/go/doc /usr/local/go/api /usr/local/go/pkg/obj

COPY --from=gobuilder /tmp/desk /app/bin/desk
COPY --from=gobuilder /tmp/legacy /app/bin/legacy
# Sealed independent references (root-owned; not agent-writable).
COPY --from=gobuilder /tmp/legacy /opt/verifier/legacy
COPY scripts/ref-depth /opt/verifier/ref-depth

COPY go.mod /app/go.mod
COPY phase /app/phase
COPY zknot /app/zknot
COPY xvox /app/xvox
COPY knotr /app/knotr
COPY kernel /app/kernel
COPY desk /app/desk
COPY desk_bin /app/desk_bin
COPY legacy_bin /app/legacy_bin
COPY curves /app/curves
COPY shared /app/shared
COPY docs /app/docs
COPY data /app/data
COPY scripts /app/scripts

ENV PATH="/usr/local/go/bin:/app/bin:${PATH}" \
    TMUX_TMPDIR=/tmp \
    TERM=xterm-256color \
    XDG_CONFIG_HOME=/tmp/.config \
    DESK_ROOT=/app \
    HOME=/home/model \
    GOCACHE=/home/model/.cache/go-build \
    GOMODCACHE=/home/model/go/pkg/mod

RUN chmod 0755 /app/scripts/build.sh /app/scripts/run_desk.sh /app/scripts/ref-depth \
        /opt/verifier/ref-depth /opt/verifier/legacy \
    && chmod a-w /app/curves /app/shared /app/docs /app/data \
    && bash /app/scripts/build.sh \
    && test -x /usr/bin/tmux \
    && test -x /usr/bin/asciinema \
    && command -v desk \
    && command -v legacy \
    && chmod 0555 /app/scripts/ref-depth /opt/verifier/ref-depth /opt/verifier/legacy \
    && chmod a-w /opt/verifier /opt/verifier-requirements.txt

# Keep the container alive for Harbor/Daytona exec; avoid brittle pre-sleep checks.
CMD ["sleep", "infinity"]
