# Meridian Ridge Geomagnetic Observatory — spectral service analysis host.
# Canonical Maven base image (Terminal-Bench sanctioned list).
FROM public.ecr.aws/docker/library/maven:3.9.9-eclipse-temurin-21@sha256:3a4ab3276a087bf276f79cae96b1af04f53731bec53fb2e651aca79e4b10211e

# 1. OS packages: agent-session tooling, PostgreSQL 16, Python for the verifier.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        asciinema \
        ca-certificates \
        curl \
        postgresql \
        python-is-python3 \
        python3 \
        python3-pip \
        tmux \
    && rm -rf /var/lib/apt/lists/*

# Login shells (tmux sessions) reset PATH from /etc/profile, which drops the
# JDK directory; expose the toolchain where every shell can reach it.
RUN ln -s /opt/java/openjdk/bin/java /usr/local/bin/java \
    && ln -s /opt/java/openjdk/bin/javac /usr/local/bin/javac \
    && ln -s /opt/java/openjdk/bin/jar /usr/local/bin/jar

# 2. Verifier Python dependencies (hash-locked; no network at run time).
COPY requirements.lock /tmp/requirements.lock
RUN python3 -m pip install --no-cache-dir --break-system-packages \
        --require-hashes --no-deps -r /tmp/requirements.lock \
    && rm /tmp/requirements.lock

# 3. Seed the station Maven repository so builds run fully offline.
#    Maven artifacts are pinned to exact versions; Maven Central serves
#    immutable release artifacts, which keeps this seeding reproducible.
COPY maven/seed-pom.xml /opt/mvn-seed/pom.xml
COPY maven/SeedMain.java /opt/mvn-seed/src/main/java/SeedMain.java
RUN mvn -B -q -f /opt/mvn-seed/pom.xml package \
    && mvn -B -q org.apache.maven.plugins:maven-dependency-plugin:3.6.1:get \
        -Dartifact=org.postgresql:postgresql:42.2.5 \
    && mvn -B -q org.apache.maven.plugins:maven-dependency-plugin:3.6.1:get \
        -Dartifact=org.postgresql:postgresql:42.6.0 \
    && mvn -B -q org.apache.maven.plugins:maven-dependency-plugin:3.6.1:get \
        -Dartifact=org.postgresql:postgresql:42.7.3 \
    && mvn -B -q org.apache.maven.plugins:maven-dependency-plugin:3.6.1:get \
        -Dartifact=org.apache.commons:commons-math3:3.5 \
    && mvn -B -q org.apache.maven.plugins:maven-dependency-plugin:3.6.1:get \
        -Dartifact=com.fasterxml.jackson.core:jackson-databind:2.13.4 \
    && rm -rf /opt/mvn-seed

# 4. Station repository policy: hosts build offline from the local repository.
COPY maven/settings.xml /root/.m2/settings.xml

# 5. Cluster configuration and one-time database seed, in a single layer.
COPY db/pg_hba.conf /tmp/dbseed/pg_hba.conf
COPY db/90-meridian.conf /tmp/dbseed/90-meridian.conf
COPY db/schema.sql /tmp/dbseed/schema.sql
COPY db/registry.sql /tmp/dbseed/registry.sql
COPY db/samples.sql /tmp/dbseed/samples.sql
RUN cp /tmp/dbseed/pg_hba.conf /etc/postgresql/16/main/pg_hba.conf \
    && chown postgres:postgres /etc/postgresql/16/main/pg_hba.conf \
    && cat /tmp/dbseed/90-meridian.conf >> /etc/postgresql/16/main/postgresql.conf \
    && pg_ctlcluster 16 main start \
    && su -s /bin/bash postgres -c "createuser meridian" \
    && su -s /bin/bash postgres -c "createdb -O meridian meridian" \
    && psql -q -h 127.0.0.1 -U meridian -d meridian -v ON_ERROR_STOP=1 -f /tmp/dbseed/schema.sql \
    && psql -q -h 127.0.0.1 -U meridian -d meridian -v ON_ERROR_STOP=1 -f /tmp/dbseed/registry.sql \
    && psql -q -h 127.0.0.1 -U meridian -d meridian -v ON_ERROR_STOP=1 -f /tmp/dbseed/samples.sql \
    && pg_ctlcluster 16 main stop \
    && rm -rf /tmp/dbseed

# 6. Task files: service working tree, station archive, request fixtures.
COPY service/ /app/service/
COPY archive/ /app/archive/
COPY requests/ /app/requests/

# 7. Session bootstrap: bring the cluster up, then hand off.
COPY --chmod=0755 entrypoint.sh /usr/local/bin/entrypoint.sh

WORKDIR /app
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["sleep", "infinity"]
