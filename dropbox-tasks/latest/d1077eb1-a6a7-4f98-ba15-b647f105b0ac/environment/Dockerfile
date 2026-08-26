FROM public.ecr.aws/docker/library/gcc:13-bookworm@sha256:930f2ebe239275fa67226654cb79273ea34eee672ae61c8a39f689c37fb7ac5c

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends build-essential=12.9 ca-certificates=20230311+deb12u1 cmake=3.25.1-1 g++=4:12.2.0-3 make=4.3-4.1 python3=3.11.2-1+b1 python3-pip=23.0.1+dfsg-1 python-is-python3=3.11.2-1+deb12u1 tmux=3.3a-3 asciinema=2.2.0-1 \
    && rm -rf /var/lib/apt/lists/*

RUN PIP_BREAK_SYSTEM_PACKAGES=1 python3 -m pip install --no-cache-dir \
    pytest==8.4.1 \
    pytest-json-ctrf==0.3.5

# Keep Harbor's interactive agent shell alive after expected non-zero diagnostic commands.
RUN printf '%s\n' \
    '' \
    'if [[ $- == *i* ]]; then' \
    "  trap 'set +e; true' ERR" \
    'fi' \
    >> /root/.bashrc

COPY . /app/environment/

RUN ln -sf /app/environment/inputs /app/inputs \
    && ln -sf /app/environment/docs /app/docs \
    && install -d /app/bin /app/output

ENV PATH="/app/bin:${PATH}"
