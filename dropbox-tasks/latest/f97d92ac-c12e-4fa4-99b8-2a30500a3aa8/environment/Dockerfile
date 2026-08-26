FROM public.ecr.aws/docker/library/ubuntu:24.04@sha256:0d39fcc8335d6d74d5502f6df2d30119ff4790ebbb60b364818d5112d9e3e932

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        asciinema \
        jq \
        opensc \
        openssl \
        python3 \
        python3-cryptography \
        python3-pykcs11 \
        python3-pytest=7.4.4-1 \
        softhsm2 \
        tmux \
    && rm -rf /var/lib/apt/lists/*

ENV SOFTHSM2_CONF=/app/ceremony/softhsm2.conf
WORKDIR /app
COPY ceremony /app/ceremony

RUN set -eux; \
    mkdir -p /app/bin /app/ceremony/tokens; \
    openssl req -x509 -newkey rsa:2048 -nodes -sha256 -days 3650 \
        -subj "/CN=Retiring Settlement Key/O=Example Payments" \
        -keyout /tmp/retiring-key.pem -out /tmp/retiring-cert.pem; \
    openssl req -x509 -newkey rsa:3072 -nodes -sha256 -days 3650 \
        -subj "/CN=Incoming Settlement Key/O=Example Payments" \
        -keyout /app/ceremony/incoming-key.pem \
        -out /app/ceremony/incoming-cert.pem; \
    openssl req -x509 -newkey rsa:3072 -nodes -sha256 -days 3650 \
        -subj "/CN=Settlement Escrow Authority/O=Example Payments" \
        -keyout /tmp/escrow-key.pem -out /tmp/escrow-cert.pem; \
    openssl req -x509 -newkey rsa:2048 -nodes -sha256 -days 3650 \
        -subj "/CN=Independent Primary Audit Anchor/O=Example Payments" \
        -keyout /tmp/audit-primary-key.pem -out /tmp/audit-primary-cert.pem; \
    openssl req -x509 -newkey rsa:2048 -nodes -sha256 -days 3650 \
        -subj "/CN=Independent Escrow Audit Anchor/O=Example Payments" \
        -keyout /tmp/audit-escrow-key.pem -out /tmp/audit-escrow-cert.pem; \
    softhsm2-util --init-token --free --label SETTLEMENT-CEREMONY \
        --so-pin C3remony-SO-741 --pin S1gner-Token-284 >/dev/null; \
    softhsm2-util --init-token --free --label SETTLEMENT-ESCROW \
        --so-pin Escrow-SO-852 --pin Escrow-Token-593 >/dev/null; \
    softhsm2-util --import /tmp/retiring-key.pem \
        --token SETTLEMENT-CEREMONY --pin S1gner-Token-284 \
        --id 10a0 --label settlement-2025-retiring >/dev/null; \
    softhsm2-util --import /tmp/escrow-key.pem \
        --token SETTLEMENT-ESCROW --pin Escrow-Token-593 \
        --id 40b0 --label settlement-escrow-private >/dev/null; \
    pkcs11-tool --module /usr/lib/softhsm/libsofthsm2.so \
        --token-label SETTLEMENT-CEREMONY --login --pin S1gner-Token-284 \
        --delete-object --type pubkey --id 10a0 >/dev/null; \
    pkcs11-tool --module /usr/lib/softhsm/libsofthsm2.so \
        --token-label SETTLEMENT-ESCROW --login --pin Escrow-Token-593 \
        --delete-object --type pubkey --id 40b0 >/dev/null; \
    openssl x509 -in /tmp/retiring-cert.pem -outform DER -out /tmp/retiring-cert.der; \
    openssl x509 -in /tmp/escrow-cert.pem -outform DER -out /tmp/escrow-cert.der; \
    openssl x509 -in /tmp/audit-primary-cert.pem -outform DER -out /tmp/audit-primary-cert.der; \
    openssl x509 -in /tmp/audit-escrow-cert.pem -outform DER -out /tmp/audit-escrow-cert.der; \
    pkcs11-tool --module /usr/lib/softhsm/libsofthsm2.so \
        --token-label SETTLEMENT-CEREMONY --login --pin S1gner-Token-284 \
        --write-object /tmp/retiring-cert.der --type cert \
        --id 10a0 --label settlement-2025-cert >/dev/null; \
    pkcs11-tool --module /usr/lib/softhsm/libsofthsm2.so \
        --token-label SETTLEMENT-CEREMONY --login --pin S1gner-Token-284 \
        --write-object /tmp/audit-primary-cert.der --type cert \
        --id ee01 --label independent-primary-audit-anchor >/dev/null; \
    pkcs11-tool --module /usr/lib/softhsm/libsofthsm2.so \
        --token-label SETTLEMENT-ESCROW --login --pin Escrow-Token-593 \
        --write-object /tmp/escrow-cert.der --type cert \
        --id 40b0 --label settlement-escrow-cert >/dev/null; \
    pkcs11-tool --module /usr/lib/softhsm/libsofthsm2.so \
        --token-label SETTLEMENT-ESCROW --login --pin Escrow-Token-593 \
        --write-object /tmp/audit-escrow-cert.der --type cert \
        --id ee02 --label independent-escrow-audit-anchor >/dev/null; \
    printf 'retiring-key build probe\n' >/tmp/retiring-probe; \
    pkcs11-tool --module /usr/lib/softhsm/libsofthsm2.so \
        --token-label SETTLEMENT-CEREMONY --login --pin S1gner-Token-284 \
        --sign --mechanism SHA256-RSA-PKCS --id 10a0 \
        --input-file /tmp/retiring-probe --output-file /tmp/retiring-probe.sig >/dev/null; \
    openssl x509 -in /tmp/retiring-cert.pem -pubkey -noout -out /tmp/retiring-public.pem; \
    openssl dgst -sha256 -verify /tmp/retiring-public.pem \
        -signature /tmp/retiring-probe.sig /tmp/retiring-probe >/dev/null; \
    printf 'escrow-key build probe\n' >/tmp/escrow-probe; \
    pkcs11-tool --module /usr/lib/softhsm/libsofthsm2.so \
        --token-label SETTLEMENT-ESCROW --login --pin Escrow-Token-593 \
        --sign --mechanism SHA256-RSA-PKCS --id 40b0 \
        --input-file /tmp/escrow-probe --output-file /tmp/escrow-probe.sig >/dev/null; \
    openssl x509 -in /tmp/escrow-cert.pem -pubkey -noout -out /tmp/escrow-public.pem; \
    openssl dgst -sha256 -verify /tmp/escrow-public.pem \
        -signature /tmp/escrow-probe.sig /tmp/escrow-probe >/dev/null; \
    openssl rand 32 >/tmp/recovery-probe; \
    openssl pkeyutl -encrypt -pubin -inkey /tmp/escrow-public.pem \
        -in /tmp/recovery-probe -out /tmp/recovery-probe.wrapped \
        -pkeyopt rsa_padding_mode:oaep -pkeyopt rsa_oaep_md:sha1 \
        -pkeyopt rsa_mgf1_md:sha1; \
    pkcs11-tool --module /usr/lib/softhsm/libsofthsm2.so \
        --token-label SETTLEMENT-ESCROW --login --pin Escrow-Token-593 \
        --decrypt --mechanism RSA-PKCS-OAEP \
        --hash-algorithm SHA-1 --mgf MGF1-SHA1 --id 40b0 \
        --input-file /tmp/recovery-probe.wrapped \
        --output-file /tmp/recovery-probe.clear >/dev/null; \
    cmp /tmp/recovery-probe /tmp/recovery-probe.clear; \
    chmod 600 /app/ceremony/incoming-key.pem; \
    shred -u /tmp/retiring-key.pem /tmp/escrow-key.pem \
        /tmp/audit-primary-key.pem /tmp/audit-escrow-key.pem \
        /tmp/recovery-probe /tmp/recovery-probe.clear; \
    rm -f /tmp/*.der /tmp/*-cert.pem /tmp/*-public.pem \
        /tmp/*-probe /tmp/*-probe.sig /tmp/recovery-probe.wrapped
