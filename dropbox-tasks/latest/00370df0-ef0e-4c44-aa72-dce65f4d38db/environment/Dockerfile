FROM public.ecr.aws/docker/library/node:22-bookworm-slim@sha256:f3a68cf41a855d227d1b0ab832bed9749469ef38cf4f58182fb8c893bc462383

WORKDIR /app

ENV DEBIAN_FRONTEND=noninteractive \
    SOURCE_DATE_EPOCH=1767225600 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends python3=3.11.2-1+b1 \
    python3-pip=23.0.1+dfsg-1 \
    python3-venv=3.11.2-1+b1 \
    asciinema=2.2.0-1 \
    brotli=1.0.9-2+b6 \
    ca-certificates=20230311+deb12u1 \
    libharfbuzz0b=6.0.0+dfsg-3 \
    libharfbuzz-bin=6.0.0+dfsg-3 \
    tmux=3.3a-3 \
    unzip=6.0-28 \
    woff2=1.0.2-2 \
    zip=3.0-13 \
    && rm -rf /var/lib/apt/lists/* \
    && python3 -m venv /opt/font-tools \
    && /opt/font-tools/bin/pip install \
       "fonttools[ufo,lxml,woff]==4.56.0" \
       ufoLib2==0.16.1 \
       fontMath==0.9.4 \
       ufo2ft==3.3.1 \
       glyphsLib==6.9.5 \
       fontmake==3.10.0 \
       opentype-sanitizer==9.1.0 \
       pytest==8.4.1 \
       pytest-json-ctrf==0.3.5 \
    && ln -sf /opt/font-tools/bin/pytest /usr/local/bin/pytest \
    && ln -sf /opt/font-tools/bin/fontmake /usr/local/bin/fontmake \
    && ln -sf /opt/font-tools/bin/fonttools /usr/local/bin/fonttools \
    && ln -sf /opt/font-tools/bin/ttx /usr/local/bin/ttx \
    && ln -sf /opt/font-tools/bin/pyftsubset /usr/local/bin/pyftsubset \
    && ln -sf /opt/font-tools/lib/python3.11/site-packages/ots/ots-sanitize /usr/local/bin/ots-sanitize \
    && ln -sf /opt/font-tools/bin/pyftmerge /usr/local/bin/pyftmerge \
    && chmod +x /usr/local/bin/ots-sanitize \
    && ots-sanitize --version || true

ENV PATH="/opt/font-tools/bin:${PATH}"

COPY asterism-bundle.tgz /tmp/asterism-bundle.tgz

RUN mkdir -p /app \
    && tar -xzf /tmp/asterism-bundle.tgz -C /app \
    && rm -f /tmp/asterism-bundle.tgz \
    && tar -xzf /app/foundry-sources.tgz -C /app \
    && rm -f /app/foundry-sources.tgz \
    && mkdir -p /app/proof-strings \
    && tar -xzf /app/proof-corpora.tgz -C /app/proof-strings \
    && rm -f /app/proof-corpora.tgz \
    && mkdir -p /app/forge-kit \
    && tar -xzf /app/forge-kit-notes.tgz -C /app/forge-kit \
    && rm -f /app/forge-kit-notes.tgz \
    && tar -xzf /app/ledger-aux.tgz -C /app/asterism-ledger \
    && rm -f /app/ledger-aux.tgz \
    && mkdir -p /app/out/colr-crate \
    && chmod a-w /app/asterism-spec/RELEASE_CONTRACT.md \
    && find /app/foundry-sources /app/asterism-ledger /app/proof-strings -type f -exec chmod a-w {} + \
    && find /app/forge-kit -type f -exec chmod a-w {} +

CMD ["bash"]
