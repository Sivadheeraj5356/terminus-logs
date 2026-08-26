#!/bin/bash
# Build the fixture repositories. Runs at image build time and (idempotently)
# from the oracle at solve time.
#
#   /app/repos/payments-stack  primary fixture
#   /app/repos/hook-broken     secondary fixture (defective pre-push marker)
set -euo pipefail

REPOS=/app/repos
KEYS=/app/keys

export GIT_AUTHOR_NAME="CDSS Author"
export GIT_AUTHOR_EMAIL="author@cdss.example"
export GIT_COMMITTER_NAME="CDSS Committer"
export GIT_COMMITTER_EMAIL="committer@cdss.example"

mkdir -p "$GNUPGHOME"
chmod 700 "$GNUPGHOME"

gpg --batch --yes --import "$KEYS"/gate_signer_A.asc \
                             "$KEYS"/gate_signer_B.asc \
                             "$KEYS"/gate_signer_C.asc \
                             >/dev/null 2>&1
gpg --import-ownertrust "$KEYS/ownertrust.txt" >/dev/null 2>&1

if ! gpg --list-keys --with-colons | grep -q '^uid.*Gate Signer Unapproved'; then
    cat >/tmp/gpg-batch-U.txt <<EOF
%no-protection
Key-Type: EDDSA
Key-Curve: ed25519
Key-Usage: sign
Name-Real: Gate Signer Unapproved
Name-Email: U@gate.example
Expire-Date: 0
%commit
EOF
    gpg --batch --generate-key /tmp/gpg-batch-U.txt >/dev/null 2>&1
    rm /tmp/gpg-batch-U.txt
fi

FP_A=942607601B2B8AD9D8EB26A7574D706A78FF540D
FP_B=DF25FE22A636F090D6443D9B9561D6AF8BF3A3C3
FP_C=ECB920EA86252FA81CE4FBF623BC54402BB0A9DC
FP_U=$(gpg --list-keys --with-colons U@gate.example | awk -F: '/^fpr/{print $10; exit}')

STANDARD_SHA=$(sha256sum /app/standard/cdss_v4.md | awk '{print $1}')

# Deterministic pinned image digest — used verbatim across all base services;
# release-gate evaluation does not fetch the image, so any digest of the
# correct shape suffices.
PIN="sha256:0e7a76c893f22fd3d1fd53497c88b91af9f0d1057b1e6ba6faf7ff5b2c6ecbcd"

emit_compose_pair() {
    local dir="$1"
    cat >"$dir/docker-compose.yml" <<YML
services:
  web:
    image: nginx@${PIN}
    labels:
      cdss.tier: web
    read_only: true
    cap_drop: [ALL]
    ports:
      - "8080:80"

  worker:
    image: alpine@${PIN}
    labels:
      cdss.tier: internal
    read_only: true
    cap_drop: [ALL]

  db:
    image: postgres@${PIN}
    labels:
      cdss.tier: infra
    read_only: true
    cap_drop: [ALL]
    tmpfs:
      - /tmp

  payments-api:
    image: paymentapi@${PIN}
    labels:
      cdss.tier: web
    read_only: true
    cap_drop: [ALL]
    ports:
      - "8443:8443"
YML

    cat >"$dir/docker-compose.prod.yml" <<YML
services:
  cache:
    image: redis@${PIN}
    labels:
      cdss.tier: infra
      cdss.class: cache
    cap_drop: [ALL]
    ports:
      - "6379:6379"
YML
}

emit_hooks() {
    local dir="$1"
    local sha="$2"
    mkdir -p "$dir/.githooks"
    cat >"$dir/.githooks/pre-push" <<HOOK
#!/bin/sh
# CDSS-STANDARD-SHA256: $sha
exit 0
HOOK
    chmod +x "$dir/.githooks/pre-push"
}

build_repo() {
    local repo="$1"
    local hook_ok="$2"
    rm -rf "$repo"
    mkdir -p "$repo"
    (
        cd "$repo"
        git init -q -b main
        git config core.hooksPath .githooks
        git config user.email "committer@cdss.example"
        git config user.name "CDSS Committer"
        git config gpg.program gpg
        git config commit.gpgsign false
        git config tag.gpgsign false

        emit_compose_pair "$repo"
        if [ "$hook_ok" = "true" ]; then
            emit_hooks "$repo" "$STANDARD_SHA"
        else
            emit_hooks "$repo" "0000000000000000000000000000000000000000000000000000000000000000"
        fi
        echo "payments-stack" >README.md

        GIT_AUTHOR_DATE="2026-02-10T09:00:00Z" \
        GIT_COMMITTER_DATE="2026-02-10T09:00:00Z" \
            git add -A && \
        GIT_AUTHOR_DATE="2026-02-10T09:00:00Z" \
        GIT_COMMITTER_DATE="2026-02-10T09:00:00Z" \
            git commit -q -m "seed compose stack"

        GIT_COMMITTER_DATE="2026-06-01T10:00:00Z" \
            git tag -s -u "$FP_A" -m "v2.1.0" release/v2.1.0

        GIT_COMMITTER_DATE="2026-06-02T10:00:00Z" \
            git tag -a -m "v2.2.0" release/v2.2.0-unsigned

        GIT_COMMITTER_DATE="2026-06-03T10:00:00Z" \
            git tag -s -u "$FP_U" -m "v2.3.0" release/v2.3.0-unapproved

        GIT_COMMITTER_DATE="2026-04-06T09:00:00Z" \
            git tag -s -u "$FP_C" -m "v2.4.0" release/v2.4.0-compromised

        GIT_COMMITTER_DATE="2026-03-11T09:00:00Z" \
            git tag -s -u "$FP_B" -m "v2.5.0" release/v2.5.0-rotated-grace

        GIT_COMMITTER_DATE="2026-03-14T09:00:00Z" \
            git tag -s -u "$FP_B" -m "v2.5.1" release/v2.5.1-rotated-late
    )
}

build_repo "$REPOS/payments-stack" "true"
build_repo "$REPOS/hook-broken"    "false"

echo "[build_repo_fixture] standard sha=$STANDARD_SHA"
