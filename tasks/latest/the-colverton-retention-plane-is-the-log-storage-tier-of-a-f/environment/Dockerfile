FROM public.ecr.aws/docker/library/eclipse-temurin:21-jdk-jammy@sha256:25d1276565738d3c805e632a4542c3a7598866ef967f4def6544c15de3a74b14
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates python3 python3-pip python3-venv tmux asciinema && rm -rf /var/lib/apt/lists/*
COPY requirements.lock /tmp/requirements.lock
RUN python3 -m pip install --no-cache-dir --require-hashes --no-deps -r /tmp/requirements.lock
WORKDIR /app
COPY --chmod=0777 app/ /app/
RUN mkdir -p /app/bin /app/output /app/build && chmod 0777 /app/bin /app/output /app/build && cd /app && find src -name '*.java' > sources.list && javac -d /app/build @sources.list && jar --create --file /app/bin/spoolward.jar --main-class=com.spoolward.Main -C /app/build . && java -jar /app/bin/spoolward.jar --selfcheck
CMD ["/bin/bash"]
