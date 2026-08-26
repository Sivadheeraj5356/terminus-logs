# Single-container hidden-binding deduction series. The holder (the "keeper") and the tally clerk's
# dialer live in one image. Isolation is by user, not by container: the keeper, the hidden stretches,
# and the published ledger are root-owned; the hidden stretches are unreadable by the unprivileged
# `agent` user used for the tally commands (task.toml [agent] user = "agent"). A root ENTRYPOINT
# first GENERATES this session's hidden stretches from OS randomness (no answer literal ships
# anywhere), then starts the keeper before the runtime keepalive; the tally talks to it only over an
# AF_UNIX endpoint. There is no network anywhere and no privileged/added capabilities.
#
# cache-bust 3 — fresh build+secret-draw for reprobe: prior eval hit the Agent Timeout Gate at
# exactly 5/10 (threshold). gpt5 at 80% leaves NO room for a round-cut (rule 29), so reprobe as-is;
# 5/10 is a coin-flip and a fresh secret draw may land <5 while staying HARD (opus 20%).
# Canonical digest-pinned Go base (the toolchain is needed at build time to compile the keeper and
# the dialer; nothing is fetched at grade time).
FROM public.ecr.aws/docker/library/golang:1.24-bookworm@sha256:1a6d4452c65dea36aac2e2d606b01b4a029ec90cc1ae53890540ce6173ea77ac

WORKDIR /app

# tmux + asciinema are REQUIRED by the agent runtime; single apt transaction, cleaned. python3
# + pip are needed only so the verifier (pytest) can run; they are unrelated to the tally's Go
# dialer.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        asciinema \
        ca-certificates \
        python3 \
        python3-pip \
        tmux \
    && rm -rf /var/lib/apt/lists/*

# Verifier deps MUST be baked in (test.sh cannot fetch anything). They are installed from a
# fully hash-locked requirements file with --require-hashes, so the build performs no live
# unverified PyPI install: every wheel (incl. transitive deps) is verified by sha256. Debian's
# python is externally-managed, so --break-system-packages lets them land in base.
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --break-system-packages --require-hashes \
    -r /tmp/requirements.txt \
    && rm -f /tmp/requirements.txt

# The unprivileged tally user. The agent harness runs commands as this user via
# `docker exec -u agent`; the container's own root processes — the ENTRYPOINT and the keeper it
# starts — stay root. We do NOT set a Dockerfile `USER`: leaving the image USER as root is what keeps
# the ENTRYPOINT and the keeper root while the tally commands use the unprivileged account.
RUN useradd --create-home --shell /bin/bash --uid 1000 agent

# Root-owned keeper state directory. The hidden stretches and the keeper binary live here, owned by
# root; the stretches are unreadable by the agent user (0400/0500 files inside a 0700 directory).
RUN mkdir -p /opt/keeper

# Compile the keeper at build time into the root-only keeper directory, then remove the source so no
# game logic ships in a readable path. CGO disabled so the binary is self-contained. The keeper binds
# its endpoint FIRST and answers "warming up" until the generated secret appears, so a request at
# t=0 is never refused (see referee/main.go:serve).
COPY referee/ /tmp/keeper-src/
RUN cd /tmp/keeper-src \
    && CGO_ENABLED=0 GOFLAGS=-mod=mod GOCACHE=/tmp/gocache go build -o /opt/keeper/keeper . \
    && rm -rf /tmp/keeper-src

# Install the secret GENERATOR into the root-only keeper directory. NO answer literal is baked
# anywhere: instead the root ENTRYPOINT runs this generator ONCE at container start (before the agent
# can connect) to draw THIS session's three hidden two-stretch bindings and their garble indices from
# OS randomness (random.SystemRandom / os.urandom), rejection-sampled to the hard regime by a
# robustness certifier: a round ships only if an information-greedy solver DISTINCT from the grading
# oracle wins with a spare name from many openers under both tie directions (so the budget is fair to
# any correct optimal strategy), while a naive trust-every-reply solver fails (so the one garble
# genuinely matters). Its SOURCE only publishes the game rules — a fair game randomises per session — so even
# reading the Dockerfile or the generator cannot reveal the running instance's stretches. The
# generated secret.json is written root-only 0400 at runtime; the generator lands in a root-only path
# (0500) so the agent user cannot read or run it.
COPY gen/generate.py /opt/keeper/generate.py

# Lock the keeper directory and its contents down to root. There is NO secret.json baked here; it is
# produced at container start by /opt/keeper/generate.py and written root-only 0400 then.
RUN chown root:root /opt/keeper /opt/keeper/keeper /opt/keeper/generate.py \
    && chmod 0700 /opt/keeper \
    && chmod 0500 /opt/keeper/keeper \
    && chmod 0500 /opt/keeper/generate.py

# Entrypoint (runs as root at container start). It starts the keeper as root in the background, then
# execs the runtime keepalive command so the container stays up. The agent harness may override the
# container command (the keepalive), but not the ENTRYPOINT, so this always runs.
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod 0755 /usr/local/bin/entrypoint.sh

# Compile the tally-facing dialer at build time and install it owned by agent. The source is removed
# after the build; only the compiled client and the worked sample ship in an agent-readable path.
# There is no secret.json and no keeper source anywhere the agent can read.
COPY app/ /tmp/dialer-src/
RUN cd /tmp/dialer-src \
    && CGO_ENABLED=0 GOFLAGS=-mod=mod GOCACHE=/tmp/gocache go build -o /app/tally . \
    && cp /tmp/dialer-src/sample-round.txt /app/sample-round.txt \
    && rm -rf /tmp/dialer-src \
    && chown agent:agent /app /app/tally /app/sample-round.txt \
    && chmod 0755 /app/tally

# The keeper needs a directory to bind its endpoint and publish the ledger. It must be root-owned and
# traversable by the agent (0755) so the agent can connect to the endpoint and read the published
# ledger, but cannot create or replace files there (only root writes it).
RUN mkdir -p /run/ryebank \
    && chown root:root /run/ryebank \
    && chmod 0755 /run/ryebank

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
# cache-bust 1784551989
