# syntax=docker/dockerfile:1.7
#
# Canonical Terminal-Bench Java (JDK) runtime — exact digest from
# "Dockerfile & Image Best Practices" §2 (Java / eclipse-temurin family):
# public.ecr.aws/docker/library/eclipse-temurin:21-jdk-jammy@sha256:25d1276565738d3c805e632a4542c3a7598866ef967f4def6544c15de3a74b14

FROM public.ecr.aws/docker/library/eclipse-temurin:21-jdk-jammy@sha256:25d1276565738d3c805e632a4542c3a7598866ef967f4def6544c15de3a74b14

LABEL org.opencontainers.image.source="https://github.com/laude-institute/terminus"
LABEL org.opencontainers.image.title="jextract-ffm-classifier-reactor"
LABEL org.opencontainers.image.description="Java jextract FFM classifier reactor for Terminal-Bench"
LABEL org.opencontainers.image.licenses="MIT"
LABEL org.opencontainers.image.version="1.0.0"

WORKDIR /app

# 1. OS/system packages (tmux + asciinema required for agent session)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        asciinema=2.1.0-1 \
        ca-certificates=20260601~22.04.1 \
        passwd=1:4.8.1-2ubuntu2.2 \
        python-is-python3=3.9.2-2 \
        python3=3.10.6-1~22.04.1 \
        python3-pip=22.0.2+dfsg-1ubuntu0.7 \
        tmux=3.2a-4ubuntu0.2 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --system --create-home --uid 10001 --shell /usr/sbin/nologin tbagent

# 2. Verifier deps pinned at build time (allow_internet = false; not installed in test.sh)
RUN pip3 install --no-cache-dir \
    pytest==8.4.1 \
    pytest-json-ctrf==0.3.5

RUN mkdir -p /app/bin /app/classes /app/output /app/work /var/lib/verifier

# 3. Entrypoint + sources (narrow COPY; metadata-preserving chmod only where needed)
COPY --chmod=0755 launcher /app/bin/reactor
COPY --chmod=0755 ops/ /app/ops/
COPY loom/ /app/loom/
COPY hearth/ /app/hearth/
COPY anvil/ /app/anvil/
COPY pulse/ /app/pulse/
COPY brace/ /app/brace/
COPY span/ /app/span/
COPY probe/ /app/probe/
COPY modules/ /app/modules/
COPY data/ /app/data/
COPY reactor/ /app/reactor/

# 4. Compile packaging stages into the image (agent may recompile after edits)
RUN find loom hearth anvil pulse brace span probe -name '*.java' > /tmp/sources.list \
    && javac -d /app/classes @/tmp/sources.list \
    && rm -f /tmp/sources.list
