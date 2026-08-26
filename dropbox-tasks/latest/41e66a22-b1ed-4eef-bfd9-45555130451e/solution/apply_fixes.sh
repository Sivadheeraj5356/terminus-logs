#!/usr/bin/env bash
set -euo pipefail

apply_ring() {
  cat > /app/environment/core/kz/ring.cpp <<'EOF'
#include "ring.hpp"
#include <cstring>

static void copy_cred(struct kz_ctx *ctx, const uint8_t *cred, size_t n) {
  size_t copy_n = n < sizeof(ctx->last_cred) ? n : sizeof(ctx->last_cred);
  std::memcpy(ctx->last_cred, cred, copy_n);
  ctx->last_n = copy_n;
}

static void revoke_prior(struct kz_ctx *ctx) {
  if (ctx->sealed_gen != 0) {
    ctx->prior_gen = ctx->sealed_gen;
  }
  ctx->prior_admit_ok = 0;
  ctx->dual_open = 0;
}

static int validate_seal_input(struct kz_ctx *ctx, uint64_t gen, const uint8_t *cred, size_t n) {
  if (!ctx || !cred || n == 0) {
    return -1;
  }
  if (gen == 0) {
    return -2;
  }
  if (ctx->sealed_gen != 0 && gen < ctx->sealed_gen) {
    return -3;
  }
  return 0;
}

int seal_ring_v(struct kz_ctx *ctx, uint64_t gen, const uint8_t *cred, size_t n) {
  int rc = validate_seal_input(ctx, gen, cred, n);
  if (rc != 0) {
    return rc;
  }
  revoke_prior(ctx);
  ctx->sealed_gen = gen;
  ctx->active_gen = gen;
  copy_cred(ctx, cred, n);
  if (ctx->prior_admit_ok != 0 || ctx->dual_open != 0) {
    ctx->prior_admit_ok = 0;
    ctx->dual_open = 0;
  }
  return 0;
}
EOF
}
apply_latch() {
  cat > /app/environment/lane/ep/latch.cpp <<'EOF'
#include "latch.hpp"
#include <algorithm>

static uint64_t soft_from(uint64_t last_activity, uint64_t soft_span) {
  return last_activity + soft_span;
}

static uint64_t compose_min(uint64_t abs_deadline, uint64_t soft_deadline) {
  return std::min(abs_deadline, soft_deadline);
}

int latch_dur_q(struct ep_ctx *ctx, uint64_t gen, uint64_t abs_deadline, uint64_t idle_base) {
  if (!ctx) {
    return -1;
  }
  (void)idle_base;
  ctx->gen = gen;
  ctx->synced_gen = gen;
  if (abs_deadline != 0) {
    ctx->abs_deadline = abs_deadline;
  } else if (ctx->abs_deadline == 0) {
    ctx->abs_deadline = ctx->issued_at + ctx->abs_span;
  }
  ctx->soft_deadline = soft_from(ctx->last_activity, ctx->soft_span);
  ep_compose(ctx);
  return 0;
}

void ep_soft_refresh(struct ep_ctx *ctx, uint64_t now) {
  if (!ctx) {
    return;
  }
  if (now < ctx->last_activity) {
    return;
  }
  ctx->last_activity = now;
  ctx->soft_deadline = soft_from(now, ctx->soft_span);
}

void ep_compose(struct ep_ctx *ctx) {
  if (!ctx) {
    return;
  }
  if (ctx->soft_deadline == 0) {
    ctx->soft_deadline = soft_from(ctx->last_activity, ctx->soft_span);
  }
  ctx->composed = compose_min(ctx->abs_deadline, ctx->soft_deadline);
}
EOF
}
apply_quota() {
  cat > /app/environment/lane/nx/quota.cpp <<'EOF'
#include "quota.hpp"

static int fence_matches(const struct nx_ctx *ctx, uint64_t fence) {
  return fence == ctx->expected_fence;
}

static int would_exceed(const struct nx_ctx *ctx, int next) {
  return next > ctx->limit;
}

int fold_cap_m(struct nx_ctx *ctx, uint32_t principal_id, int delta, uint64_t fence) {
  if (!ctx) {
    return -1;
  }
  if (principal_id != ctx->principal_id) {
    return -2;
  }
  if (!fence_matches(ctx, fence)) {
    return -3;
  }
  int next = ctx->occupancy + delta;
  if (next < 0) {
    next = 0;
  }
  if (would_exceed(ctx, next)) {
    return -4;
  }
  ctx->occupancy = next;
  ctx->fence = fence;
  if (ctx->held_after_reload) {
    ctx->held_after_reload = 0;
  }
  return 0;
}
EOF
}
apply_pack() {
  cat > /app/environment/tools/sf_verify/pack.cpp <<'EOF'
#include "pack.hpp"
#include <sstream>

static void write_row(std::ostringstream &oss, const run_row &r, bool trailing_comma) {
  oss << "    {\"bundle\": \"" << r.bundle << "\", "
      << "\"profile\": \"" << r.profile << "\", "
      << "\"gen\": " << r.gen << ", "
      << "\"synced_gen\": " << r.synced_gen << ", "
      << "\"dual_valid\": " << r.dual_valid << ", "
      << "\"dual_peak\": " << r.dual_peak << ", "
      << "\"status\": \"" << r.status << "\", "
      << "\"composed\": " << r.composed << ", "
      << "\"abs_deadline\": " << r.abs_deadline << ", "
      << "\"occupancy\": " << r.occupancy << ", "
      << "\"limit\": " << r.limit << ", "
      << "\"digest_key\": \"" << r.digest_key << "\", "
      << "\"digest_sha256\": \"" << r.digest_sha256 << "\", "
      << "\"journal_tag\": \"" << r.journal_tag << "\"}";
  if (trailing_comma) {
    oss << ",\n";
  }
}

int pack_blob_w(const struct run_matrix *mx, struct journal_blob *out) {
  if (!mx || !out) {
    return -1;
  }
  std::ostringstream oss;
  oss << "{\n";
  oss << "  \"matrix\": \"" << mx->matrix_name << "\",\n";
  oss << "  \"profiles\": [";
  for (size_t i = 0; i < mx->profiles.size(); ++i) {
    if (i) oss << ", ";
    oss << "\"" << mx->profiles[i] << "\"";
  }
  oss << "],\n";
  oss << "  \"rows\": [\n";
  for (size_t i = 0; i < mx->rows.size(); ++i) {
    write_row(oss, mx->rows[i], i + 1 < mx->rows.size());
    if (i + 1 == mx->rows.size()) {
      oss << "\n";
    }
  }
  oss << "  ],\n";
  oss << "  \"digests\": {";
  bool first = true;
  for (const auto &kv : mx->digests) {
    if (!first) oss << ", ";
    first = false;
    oss << "\"" << kv.first << "\": \"" << kv.second << "\"";
  }
  oss << "},\n";
  oss << "  \"meta\": {"
      << "\"stage_field_count\": " << mx->stage_field_count << ", "
      << "\"journal_field_count\": 14, "
      << "\"recovery_marker\": \"" << mx->recovery_marker << "\", "
      << "\"epoch_ok\": \"" << mx->epoch_ok << "\"}\n";
  oss << "}\n";
  out->json_body = oss.str();
  out->field_count = 14;
  return 0;
}
EOF
}

apply_ring
apply_latch
apply_quota
apply_pack
