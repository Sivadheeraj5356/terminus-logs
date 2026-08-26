# Canonical Terminal-Bench Maven + Temurin 21 base (public.ecr.aws/docker/library digest from PLATFORM_AUTO_EVAL).
FROM public.ecr.aws/docker/library/maven:3.9.9-eclipse-temurin-21@sha256:3a4ab3276a087bf276f79cae96b1af04f53731bec53fb2e651aca79e4b10211e

WORKDIR /app

# Edition 2 requires explicit apt version pins (scripts/run_static_checks.py).
# Refresh pins with apt-cache madison if a mirror drops a superseded version.
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3=3.12.3-0ubuntu2.1 \
    python3-venv=3.12.3-0ubuntu2.1 \
    tmux=3.4-1ubuntu0.1 \
    asciinema=2.4.0-1 \
    ca-certificates=20260601~24.04.1 \
    sqlite3=3.45.1-1ubuntu2.6 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /tmp/requirements.txt
COPY requirements.lock /tmp/requirements.lock
RUN python3 -m venv /opt/verifier \
    && /opt/verifier/bin/pip install --no-cache-dir --require-hashes --no-deps -r /tmp/requirements.txt
ENV PATH=/opt/verifier/bin:${PATH}

RUN mkdir -p /app/environment /app/output/stage /logs/verifier /app/bin

COPY pom.xml /app/environment/pom.xml
COPY docs /app/environment/docs
COPY tools /app/environment/tools
COPY corp /app/environment/corp
COPY n3 /app/environment/n3
COPY m8 /app/environment/m8
COPY t5 /app/environment/t5
COPY driver /app/environment/driver
COPY README.md /app/environment/README.md

# Public absolute paths from the task contract.
RUN ln -sfn /app/environment/corp /app/corp \
    && ln -sfn /app/environment/docs /app/docs \
    && ln -sfn /app/environment/tools /app/tools \
    && chmod +x /app/environment/tools/build_x7.sh /app/environment/tools/run_x \
    && bash /app/environment/tools/build_x7.sh \
    && mkdir -p /app/output/stage

WORKDIR /app
