#include "digest_fold.h"
#include "plan_types.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>

#define APP_ROOT "/app"
#define MAX_SCENARIOS 40

static void parse_line_kv(const char *line, int *table, uint32_t *rows, uint32_t *distinct,
                          uint32_t *buckets, uint32_t bounds[PL_MAX_BUCK], char *fp_tag,
                          int *partial, int *vis) {
  if (table) {
    *table = 0;
  }
  if (rows) {
    *rows = 0;
  }
  if (distinct) {
    *distinct = 0;
  }
  if (buckets) {
    *buckets = 4;
  }
  if (bounds) {
    for (int i = 0; i < PL_MAX_BUCK; i++) {
      bounds[i] = 0;
    }
  }
  if (fp_tag) {
    fp_tag[0] = '\0';
  }
  if (partial) {
    *partial = 0;
  }
  if (vis) {
    *vis = 0;
  }
  for (const char *tok = line; *tok; tok++) {
    if (strncmp(tok, " table=", 7) == 0 && table) {
      *table = atoi(tok + 7);
    } else if (strncmp(tok, " rows=", 6) == 0 && rows) {
      *rows = (uint32_t)atoi(tok + 6);
    } else if (strncmp(tok, " distinct=", 10) == 0 && distinct) {
      *distinct = (uint32_t)atoi(tok + 10);
    } else if (strncmp(tok, " buckets=", 9) == 0 && buckets) {
      *buckets = (uint32_t)atoi(tok + 9);
    } else if (strncmp(tok, " b0=", 4) == 0 && bounds) {
      bounds[0] = (uint32_t)atoi(tok + 4);
    } else if (strncmp(tok, " b1=", 4) == 0 && bounds) {
      bounds[1] = (uint32_t)atoi(tok + 4);
    } else if (strncmp(tok, " b2=", 4) == 0 && bounds) {
      bounds[2] = (uint32_t)atoi(tok + 4);
    } else if (strncmp(tok, " b3=", 4) == 0 && bounds) {
      bounds[3] = (uint32_t)atoi(tok + 4);
    } else if (strncmp(tok, " fp=", 4) == 0 && fp_tag) {
      strncpy(fp_tag, tok + 4, 31);
      fp_tag[31] = '\0';
    } else if (strncmp(tok, " partial=", 9) == 0 && partial) {
      *partial = atoi(tok + 9);
    } else if (strncmp(tok, " vis=", 5) == 0 && vis) {
      *vis = atoi(tok + 5);
    } else if (strncmp(tok, " gen=", 5) == 0 && vis) {
      *vis = atoi(tok + 5);
    }
  }
}

static void load_table(pl_ctx *ctx, int table, uint32_t rows, uint32_t distinct, uint32_t buckets,
                       const uint32_t *bounds) {
  if (table < 0 || table >= PL_MAX_TABLE) {
    return;
  }
  if (table >= ctx->table_n) {
    ctx->table_n = table + 1;
  }
  pl_table *t = &ctx->tables[table];
  t->rows = rows;
  t->distinct = distinct;
  t->buckets = buckets;
  for (uint32_t i = 0; i < PL_MAX_BUCK && i < buckets; i++) {
    t->bounds[i] = bounds[i];
  }
  t->stats_gen = ctx->live_gen;
}

static void analyze_table(pl_ctx *ctx, int table, uint32_t rows, uint32_t distinct) {
  if (table < 0 || table >= PL_MAX_TABLE) {
    return;
  }
  pl_table *t = &ctx->tables[table];
  uint32_t old_rows = t->rows;
  t->rows = rows;
  t->distinct = distinct;
  if (old_rows > 0 && rows != old_rows) {
    for (int i = 0; i < PL_MAX_BUCK; i++) {
      if (t->bounds[i] > 0) {
        t->bounds[i] = (t->bounds[i] * rows) / old_rows;
      }
    }
  }
  ctx->live_gen++;
  t->stats_gen = ctx->live_gen;
}

static void snap_pause(pl_ctx *ctx) {
  ctx->snap_valid = 1;
  ctx->snap_gen = ctx->live_gen;
  ctx->snap_vis_gen = ctx->vis_gen;
  for (int i = 0; i < ctx->table_n; i++) {
    ctx->snap_tables[i] = ctx->tables[i];
    for (int b = 0; b < PL_MAX_BUCK; b++) {
      ctx->snap_bounds[i][b] = ctx->tables[i].bounds[b];
    }
  }
}

static void snap_resume(pl_ctx *ctx) {
  if (!ctx->snap_valid) {
    return;
  }
  ctx->resume_pending = 1;
  for (int i = 0; i < ctx->table_n; i++) {
    ctx->tables[i].bounds[0] = ctx->snap_bounds[i][0];
    ctx->tables[i].bounds[1] = ctx->snap_bounds[i][1];
    ctx->tables[i].bounds[2] = ctx->snap_bounds[i][2];
    ctx->tables[i].bounds[3] = ctx->snap_bounds[i][3];
  }
}

static int run_tape(const char *path, int pause_mode, pl_row *out) {
  FILE *fp = fopen(path, "r");
  if (!fp) {
    return -1;
  }
  pl_ctx ctx;
  pl_reset(&ctx);
  char query_tag[32] = "q0";
  int partial_req = 0;
  char line[512];
  while (fgets(line, sizeof(line), fp)) {
    char *p = line;
    while (*p == ' ' || *p == '\t') {
      p++;
    }
    if (*p == '#' || *p == '\n' || *p == '\0') {
      continue;
    }
    char kind[32];
    if (sscanf(p, "%31s", kind) != 1) {
      continue;
    }
    if (strcmp(kind, "init") == 0) {
      int vis = 1;
      parse_line_kv(p, NULL, NULL, NULL, NULL, NULL, NULL, NULL, &vis);
      ctx.vis_gen = (uint32_t)vis;
      continue;
    }
    if (strcmp(kind, "load") == 0) {
      int table = 0;
      uint32_t rows = 0, distinct = 0, buckets = 4;
      uint32_t bounds[PL_MAX_BUCK] = {0};
      parse_line_kv(p, &table, &rows, &distinct, &buckets, bounds, NULL, NULL, NULL);
      load_table(&ctx, table, rows, distinct, buckets, bounds);
      continue;
    }
    if (strcmp(kind, "analyze") == 0) {
      int table = 0;
      uint32_t rows = 0, distinct = 0;
      parse_line_kv(p, &table, &rows, &distinct, NULL, NULL, NULL, NULL, NULL);
      analyze_table(&ctx, table, rows, distinct);
      continue;
    }
    if (strcmp(kind, "vis") == 0) {
      int v = 1;
      parse_line_kv(p, NULL, NULL, NULL, NULL, NULL, NULL, NULL, &v);
      ctx.vis_gen = (uint32_t)v;
      continue;
    }
    if (strcmp(kind, "pause") == 0) {
      if (pause_mode) {
        snap_pause(&ctx);
      }
      continue;
    }
    if (strcmp(kind, "resume") == 0) {
      if (pause_mode) {
        snap_resume(&ctx);
      }
      continue;
    }
    if (strcmp(kind, "query") == 0) {
      int partial = 0;
      parse_line_kv(p, NULL, NULL, NULL, NULL, NULL, query_tag, &partial, NULL);
      partial_req = partial;
      char alpha[32], beta[32], gamma[32];
      uint32_t stats_gen = 0;
      uint64_t fp = fold_fp(query_tag);
      drive_plan(&ctx, fp, partial_req, alpha, beta, gamma, &stats_gen);
      strncpy(out->step_alpha_id, alpha, sizeof(out->step_alpha_id) - 1);
      strncpy(out->step_beta_id, beta, sizeof(out->step_beta_id) - 1);
      strncpy(out->step_gamma_id, gamma, sizeof(out->step_gamma_id) - 1);
      out->stats_gen = stats_gen;
      out->stats_ok = (stats_gen == ctx.live_gen) ? 1 : 0;
      plan_digest_row(out, out->plan_digest, sizeof(out->plan_digest));
      strcpy(out->finish_reason, "ok");
      ctx.resume_pending = 0;
    }
  }
  fclose(fp);
  return 0;
}

static int read_schema_anchor(const char *app_root) {
  char path[512];
  snprintf(path, sizeof(path), "%s/stubs/schema_anchor.txt", app_root);
  FILE *fp = fopen(path, "r");
  if (!fp) {
    return 4207;
  }
  int v = 4207;
  fscanf(fp, "%d", &v);
  fclose(fp);
  return v;
}

static void write_report(const char *app_root, pl_row *rows, int n_rows, int schema_anchor,
                         int pair_mismatch, int step_mismatch) {
  char out_path[512];
  snprintf(out_path, sizeof(out_path), "%s/output/plan_audit.json", app_root);
  FILE *fp = fopen(out_path, "w");
  if (!fp) {
    exit(1);
  }
  int scenario_count = 0;
  char last_sid[64] = "";
  for (int i = 0; i < n_rows; i++) {
    if (strcmp(last_sid, rows[i].scenario_id) != 0) {
      scenario_count++;
      strncpy(last_sid, rows[i].scenario_id, sizeof(last_sid) - 1);
    }
  }
  fprintf(fp, "{\n  \"schema_anchor\": %d,\n  \"scenarios\": [\n", schema_anchor);
  for (int i = 0; i < n_rows; i++) {
    fprintf(fp,
            "    {\"scenario_id\": \"%s\", \"mode\": \"%s\", \"step_alpha_id\": \"%s\", "
            "\"step_beta_id\": \"%s\", \"step_gamma_id\": \"%s\", \"stats_gen\": %u, "
            "\"stats_ok\": %s, \"pair_ok\": %s, \"plan_digest\": \"%s\", "
            "\"finish_reason\": \"%s\"}",
            rows[i].scenario_id, rows[i].mode, rows[i].step_alpha_id, rows[i].step_beta_id,
            rows[i].step_gamma_id, rows[i].stats_gen, rows[i].stats_ok ? "true" : "false",
            rows[i].pair_ok ? "true" : "false", rows[i].plan_digest, rows[i].finish_reason);
    if (i + 1 < n_rows) {
      fprintf(fp, ",\n");
    } else {
      fprintf(fp, "\n");
    }
  }
  fprintf(fp,
          "  ],\n  \"summary\": {\"scenario_count\": %d, \"scenario_rows\": %d, "
          "\"pair_mismatch_count\": %d, \"step_mismatch_total\": %d}\n}\n",
          scenario_count, n_rows, pair_mismatch, step_mismatch);
  fclose(fp);
}

int main(void) {
  const char *app_root = getenv("TASK_APP_ROOT");
  if (!app_root || !*app_root) {
    app_root = APP_ROOT;
  }
  char man_path[512];
  snprintf(man_path, sizeof(man_path), "%s/data/scenarios/manifest.tsv", app_root);
  FILE *man = fopen(man_path, "r");
  if (!man) {
    fprintf(stderr, "plan_matrix: missing manifest\n");
    return 1;
  }
  char line[512];
  pl_row rows[MAX_SCENARIOS * 2];
  int n = 0;
  int pair_mismatch = 0;
  int step_mismatch = 0;
  while (fgets(line, sizeof(line), man)) {
    char sid[64];
    char rel[256];
    if (sscanf(line, "%63s %255s", sid, rel) != 2) {
      continue;
    }
    char tape_path[512];
    snprintf(tape_path, sizeof(tape_path), "%s/%s", app_root, rel);
    pl_row cont;
    memset(&cont, 0, sizeof(cont));
    strncpy(cont.scenario_id, sid, sizeof(cont.scenario_id) - 1);
    strcpy(cont.mode, "continuous");
    if (run_tape(tape_path, 0, &cont) != 0) {
      fclose(man);
      return 1;
    }
    cont.pair_ok = 1;
    rows[n++] = cont;

    pl_row pause;
    memset(&pause, 0, sizeof(pause));
    strncpy(pause.scenario_id, sid, sizeof(pause.scenario_id) - 1);
    strcpy(pause.mode, "pause_resume");
    if (run_tape(tape_path, 1, &pause) != 0) {
      fclose(man);
      return 1;
    }
    int agree = (strcmp(cont.step_alpha_id, pause.step_alpha_id) == 0 &&
                 strcmp(cont.step_beta_id, pause.step_beta_id) == 0 &&
                 strcmp(cont.step_gamma_id, pause.step_gamma_id) == 0 &&
                 cont.stats_gen == pause.stats_gen);
    pause.pair_ok = agree ? 1 : 0;
    if (!agree) {
      pair_mismatch++;
      if (strcmp(cont.step_alpha_id, pause.step_alpha_id) != 0) {
        step_mismatch++;
      }
      if (strcmp(cont.step_beta_id, pause.step_beta_id) != 0) {
        step_mismatch++;
      }
      if (strcmp(cont.step_gamma_id, pause.step_gamma_id) != 0) {
        step_mismatch++;
      }
      if (cont.stats_gen != pause.stats_gen) {
        step_mismatch++;
      }
    }
    rows[n++] = pause;
  }
  fclose(man);
  {
    char out_parent[512];
    snprintf(out_parent, sizeof(out_parent), "%s/output", app_root);
    mkdir(out_parent, 0755);
  }
  write_report(app_root, rows, n, read_schema_anchor(app_root), pair_mismatch, step_mismatch);
  return 0;
}
