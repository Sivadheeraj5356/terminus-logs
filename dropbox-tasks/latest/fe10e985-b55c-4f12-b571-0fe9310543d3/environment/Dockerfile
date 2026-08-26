ARG EFFECT_UPSTREAM_COMMIT=3e59443be029e99d2b457bb43f682feb5ebcd2e0

FROM public.ecr.aws/docker/library/node:22-bookworm-slim@sha256:f3a68cf41a855d227d1b0ab832bed9749469ef38cf4f58182fb8c893bc462383 AS artifacts-stage
ARG EFFECT_UPSTREAM_COMMIT

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        git \
    && rm -rf /var/lib/apt/lists/*

RUN corepack enable \
    && corepack prepare pnpm@10.17.1 --activate

WORKDIR /tmp/effect

RUN git clone https://github.com/Effect-TS/effect.git . \
    && git checkout "${EFFECT_UPSTREAM_COMMIT}"

RUN pnpm install


FROM public.ecr.aws/docker/library/node:22-bookworm-slim@sha256:f3a68cf41a855d227d1b0ab832bed9749469ef38cf4f58182fb8c893bc462383

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        git \
        python3 \
        python3-venv \
        make \
        g++ \
        tmux \
        asciinema \
    && rm -rf /var/lib/apt/lists/*

RUN corepack enable \
    && corepack prepare pnpm@10.17.1 --activate \
    && pnpm --version

RUN python3 -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir \
        pytest==8.4.1 \
        pytest-json-ctrf==0.3.5

ENV PATH="/opt/venv/bin:${PATH}"

COPY --from=artifacts-stage /root/.local/share/pnpm/store /root/.local/share/pnpm/store

WORKDIR /app

COPY repo/ /app/repo/

CMD ["/bin/bash"]