# Canonical Terminal-Bench base image: the approved Maven entry from the sanctioned list
# ("Build tools and SDKs" -> Maven), digest-pinned to the exact reference published there.
# It is the right base here because the agent has to compile and run the Java registry, so
# JDK 21 and Maven must both be present at runtime.
FROM public.ecr.aws/docker/library/maven:3.9.9-eclipse-temurin-21@sha256:3a4ab3276a087bf276f79cae96b1af04f53731bec53fb2e651aca79e4b10211e

ENV DEBIAN_FRONTEND=noninteractive \
    JAVA_HOME="/opt/java/openjdk" \
    MAVEN_OPTS="-Dmaven.repo.local=/root/.m2/repository" \
    PATH="/opt/venv/bin:/opt/java/openjdk/bin:${PATH}"

# 1. System packages: the agent runtime (tmux, asciinema) and the Python the verifier runs on.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        asciinema \
        ca-certificates \
        python3 \
        python3-venv \
        tmux \
    && rm -rf /var/lib/apt/lists/*

# 2. Verifier dependencies, from a fully hash-pinned lockfile, into an isolated venv.
COPY requirements.lock /tmp/requirements.lock
RUN python3 -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir --require-hashes --no-deps -r /tmp/requirements.lock \
    && rm /tmp/requirements.lock

# 3. Make the toolchain resolvable from every shell, including login shells that rebuild PATH
#    from /etc/profile and so drop the environment set above.
COPY --chmod=0644 aurora-env.sh /etc/profile.d/aurora-env.sh
RUN ln -s /opt/java/openjdk/bin/java /usr/local/bin/java \
    && ln -s /opt/java/openjdk/bin/javac /usr/local/bin/javac \
    && ln -s /opt/venv/bin/python /usr/local/bin/python \
    && ln -s /opt/venv/bin/pytest /usr/local/bin/pytest

# 4. Project manifest first, so the dependency layer survives edits to the sources.
WORKDIR /app
COPY app/pom.xml /app/pom.xml
RUN mvn -B -DskipTests dependency:go-offline

# 5. Sources and task data.
COPY app/src /app/src
COPY app/archive /app/archive
COPY app/docs /app/docs
COPY app/README.md /app/README.md
COPY --chmod=0755 app/registry /app/registry

# 6. Build once with the network available, so every plugin and plugin dependency the build
#    lifecycle needs is resident in the local repository.
RUN mvn -B -DskipTests package

# 7. Prove the offline build works: this is the exact command the agent and the verifier run,
#    and the task is unsolvable if it cannot resolve without a network.
RUN mvn -B -o -DskipTests package

# 8. The seed registry (migrations V1-V6 already applied) and a pristine copy of it.
RUN mkdir -p /app/data /app/out /opt/aurora/seed
COPY app/data/registry.mv.db /app/data/registry.mv.db
COPY app/data/registry.mv.db /opt/aurora/seed/registry.mv.db

WORKDIR /app
