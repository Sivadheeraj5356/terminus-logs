FROM public.ecr.aws/docker/library/eclipse-temurin:21-jdk-jammy@sha256:25d1276565738d3c805e632a4542c3a7598866ef967f4def6544c15de3a74b14

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       python3=3.10.6-1~22.04.1 \
       python3-venv=3.10.6-1~22.04.1 \
       tmux=3.2a-4ubuntu0.2 \
       asciinema=2.1.0-1 \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /app/lib \
    && python3 -c "import hashlib, pathlib, urllib.request; url='https://repo.maven.apache.org/maven2/org/duckdb/duckdb_jdbc/1.3.2.1/duckdb_jdbc-1.3.2.1.jar'; out=pathlib.Path('/app/lib/duckdb_jdbc.jar'); data=urllib.request.urlopen(url).read(); expected='8da972bd970fc165c246e01dc0794bf154562d31a232e4950bd66b82f8901f94'; actual=hashlib.sha256(data).hexdigest(); assert actual == expected, (actual, expected); out.write_bytes(data)"

RUN python3 -m venv /opt/verifier
RUN /opt/verifier/bin/pip install --no-cache-dir \
    iniconfig==2.1.0 \
    packaging==25.0 \
    pluggy==1.6.0 \
    Pygments==2.19.2 \
    pytest==8.4.1 \
    pytest-json-ctrf==0.3.5
ENV PATH=/opt/verifier/bin:${PATH}

WORKDIR /app/environment
COPY build.sh run.sh ./
COPY cli/ ./cli/
COPY model/ ./model/
COPY format/ ./format/
COPY ingest/ ./ingest/
COPY analysis/ ./analysis/
COPY storage/ ./storage/
COPY docs/ ./docs/
COPY fixtures/ ./fixtures/
RUN chmod +x build.sh run.sh && ./build.sh

WORKDIR /app
CMD ["bash"]
