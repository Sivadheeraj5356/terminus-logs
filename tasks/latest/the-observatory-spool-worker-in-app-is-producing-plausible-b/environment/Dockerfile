FROM public.ecr.aws/docker/library/debian:bookworm-slim@sha256:4724b8cc51e33e398f0e2e15e18d5ec2851ff0c2280647e1310bc1642182655d

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        bash=5.2.15-2+b13 \
        gawk=1:5.2.1-2 \
        coreutils=9.1-1 \
        findutils=4.9.0-4 \
        grep=3.8-5 \
        sed=4.9-1+deb12u1 \
        jq=1.6-2.1+deb12u2 \
        tmux=3.3a-3 \
        asciinema=2.2.0-1 \
        python3=3.11.2-1+b1 \
        python3-pip=23.0.1+dfsg-1 \
        python3-venv=3.11.2-1+b1 \
        locales=2.36-9+deb12u14 \
        ca-certificates=20230311+deb12u1 \
    && sed -i '/de_DE.UTF-8/s/^# //' /etc/locale.gen \
    && locale-gen de_DE.UTF-8 C.UTF-8 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-verifier.txt /tmp/requirements-verifier.txt
RUN python3 -m pip install --break-system-packages --no-cache-dir -r /tmp/requirements-verifier.txt

COPY app/ /app/
COPY seed-data/ /data/
COPY seed-data/ /seed-data/

RUN mkdir -p /output /app/bin /logs/verifier /logs/agent \
    && ln -sf /app/scripts/specz-worker /app/bin/specz-worker \
    && chmod +x /app/scripts/specz-worker /app/tools/*.sh

ENV PATH=/usr/local/bin:/usr/bin:/bin
ENV SPECZ_APP=/app
ENV SPECZ_CONFIG=/app/config/site.conf

CMD ["sleep", "infinity"]
