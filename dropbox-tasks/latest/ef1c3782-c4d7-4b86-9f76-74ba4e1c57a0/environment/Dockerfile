# Canonical digest-pinned Debian base. The gforth interpreter, the C build
# toolchain and the verifier's Python are installed from the distribution at
# BUILD time (network available now); the task itself runs offline. Single stage:
# gforth must remain in the runtime image because the offline build is assembled
# and run by the verifier at task time.
FROM public.ecr.aws/docker/library/debian:bookworm-slim@sha256:4724b8cc51e33e398f0e2e15e18d5ec2851ff0c2280647e1310bc1642182655d

LABEL org.opencontainers.image.title="NBX-03-posting-build"
LABEL org.opencontainers.image.description="Terminus 2 task: restore the offline gforth clearing-tape postings build so its report is correct for amounts of every size."

ENV DEBIAN_FRONTEND=noninteractive

# gforth = the interpreter the offline build assembles and runs.
# build-essential = the C toolchain available to the build.
# tmux + asciinema = required by the agent runtime.
# python3/venv = the verifier's pytest harness only.
RUN printf 'Acquire::Retries "5";\n' > /etc/apt/apt.conf.d/80-retries \
    && apt-get update && apt-get install -y --no-install-recommends \
        gforth \
        build-essential \
        python3 \
        python3-venv \
        tmux \
        asciinema \
        ca-certificates \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Isolated venv for the verifier's pytest (exact-pinned). Baked in at build time
# because the task runs offline (allow_internet = false).
RUN python3 -m venv /opt/verifier-venv \
    && /opt/verifier-venv/bin/pip install --no-cache-dir \
        pytest==8.3.4 \
        pytest-json-ctrf==0.3.5 \
    && rm -rf /root/.cache

WORKDIR /app
COPY app/ /app/
RUN chmod +x /app/build/assemble.sh /app/build/run.sh

# Establish the current (as-reported) state: the build completes and produces a
# report that is correct for the small shipped tape.
RUN bash /app/build/run.sh >/dev/null 2>&1

# Sanity: interpreter present and the vendored kit and decoder are in place.
RUN command -v gforth >/dev/null \
    && test -f /app/vendor/reckit/recfmt.fs \
    && test -f /app/vendor/reckit/FORMAT \
    && test -f /app/build/decode.fs \
    && test -f /app/build/tape.fs
