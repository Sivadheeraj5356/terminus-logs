FROM public.ecr.aws/docker/library/node:22-bookworm-slim@sha256:f3a68cf41a855d227d1b0ab832bed9749469ef38cf4f58182fb8c893bc462383

WORKDIR /app

# Copy dependency manifests (least volatile first)
COPY app/api/package.json app/api/package-lock.json app/api/pnpm-lock.yaml /app/api/
COPY app/Gemfile /app/Gemfile
COPY app/Rakefile /app/Rakefile
COPY requirements.lock /tmp/requirements.lock

# System dependencies + toolchain (grouped before source COPY)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        asciinema \
        ca-certificates \
        curl \
        ruby=1:3.1 \
        ruby-dev=1:3.1 \
        build-essential \
        python3=3.11.2-1+b1 \
        python3-venv \
        tmux \
    && rm -rf /var/lib/apt/lists/* \
    && corepack enable && corepack prepare pnpm@8 --activate

# Install Node dependencies
WORKDIR /app/api
RUN pnpm install 2>/dev/null || npm ci
WORKDIR /app

# Install Python verifier deps
RUN python3 -m venv /opt/verifier-venv \
    && /opt/verifier-venv/bin/pip install --no-cache-dir -r /tmp/requirements.lock

# Copy source files and build (most volatile)
COPY app/api/tsconfig.json /app/api/
COPY app/api/src/ /app/api/src/
WORKDIR /app/api
RUN npx tsc
WORKDIR /app

# Copy remaining application files
COPY app/Containerfile /app/Containerfile
COPY app/lib/ /app/lib/
COPY app/docs/ /app/docs/
COPY app/data/ /app/data/
COPY app/tools/ /app/tools/
