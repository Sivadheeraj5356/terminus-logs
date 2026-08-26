FROM public.ecr.aws/docker/library/debian:bookworm-slim@sha256:4724b8cc51e33e398f0e2e15e18d5ec2851ff0c2280647e1310bc1642182655d

ENV DEBIAN_FRONTEND=noninteractive
# All GPG operations — key import at build time and tag verification at
# request time — share this keyring so the running service sees the same
# state the fixture builder set up.
ENV GNUPGHOME=/root/.gnupg-cdss

# Runtime + toolchain: JDK for compilation and runtime; git + gnupg for tag
# evidence; python3 for the verifier venv; curl to fetch pinned jars during
# build; tmux + asciinema baked in per the offline-verifier contract; jq for
# a small self-check in solve.sh.
RUN apt-get update -q \
    && apt-get install -y --no-install-recommends \
       openjdk-17-jdk-headless \
       git gnupg \
       ca-certificates curl \
       python3 python3-venv \
       tmux asciinema jq \
    && python3 -m venv /opt/verifier-venv \
    && /opt/verifier-venv/bin/pip install --no-cache-dir \
       pytest==8.3.5 pytest-json-ctrf==0.3.5 pyyaml==6.0.2 \
    && rm -rf /var/lib/apt/lists/*

# Vendored pinned jars. Download at build time from Maven Central and verify
# each with a static sha256 before proceeding. Runtime is offline.
RUN mkdir -p /opt/jars \
    && curl -sSL -o /opt/jars/snakeyaml.jar \
        https://repo1.maven.org/maven2/org/yaml/snakeyaml/2.2/snakeyaml-2.2.jar \
    && echo "1467931448a0817696ae2805b7b8b20bfb082652bf9c4efaed528930dc49389b  /opt/jars/snakeyaml.jar" \
        | sha256sum -c - \
    && curl -sSL -o /opt/jars/h2.jar \
        https://repo1.maven.org/maven2/com/h2database/h2/2.2.224/h2-2.2.224.jar \
    && echo "b9d8f19358ada82a4f6eb5b174c6cfe320a375b5a9cb5a4fe456d623e6e55497  /opt/jars/h2.jar" \
        | sha256sum -c -

WORKDIR /app
COPY app/ /app/

RUN chmod +x /app/build.sh /app/scripts/*.sh

# Compile once at build time so the shipped image has gate.jar plus the
# seeded H2 file. The oracle rebuilds gate.jar after replacing the stubs.
RUN /app/build.sh

# Build the deterministic fixture repos.
RUN /app/scripts/build_repo_fixture.sh

# Keep the container alive if launched interactively by the agent runner.
CMD ["sleep", "infinity"]
