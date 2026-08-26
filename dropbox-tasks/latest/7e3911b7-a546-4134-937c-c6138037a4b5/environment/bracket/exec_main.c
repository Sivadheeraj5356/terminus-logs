#include "mesh_types.h"
#include "mesh_fold.h"
#include "harness_lane.h"

#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>

#define APP_ROOT "/app"
#define MAX_SCENARIOS 24
#define SCHEMA_FALLBACK 9287

static void fill_sphere(ms_ctx *ctx, int cx, int cy, int cz, double r, uint16_t val) {
  for (int z = 0; z < ctx->nz; z++) {
    for (int y = 0; y < ctx->ny; y++) {
      for (int x = 0; x < ctx->nx; x++) {
        double dx = (double)x - cx;
        double dy = (double)y - cy;
        double dz = (double)z - cz;
        if (dx * dx + dy * dy + dz * dz <= r * r) {
          ctx->field[ms_idx(ctx, x, y, z)] = val;
        }
      }
    }
  }
}

static void fill_box(ms_ctx *ctx, int x0, int y0, int z0, int x1, int y1, int z1, uint16_t val) {
  for (int z = z0; z <= z1; z++) {
    for (int y = y0; y <= y1; y++) {
      for (int x = x0; x <= x1; x++) {
        if (x >= 0 && y >= 0 && z >= 0 && x < ctx->nx && y < ctx->ny && z < ctx->nz) {
          ctx->field[ms_idx(ctx, x, y, z)] = val;
        }
      }
    }
  }
}

static int run_tape(const char *path, int pause_mode, ms_row *out) {
  FILE *fp = fopen(path, "r");
  if (!fp) {
    return -1;
  }
  ms_ctx ctx;
  ms_reset(&ctx);
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
    char a[64];
    char b[64];
    int n = sscanf(p, "%31s %63s %63s", kind, a, b);
    if (strcmp(kind, "init") == 0) {
      int nx = 10, ny = 10, nz = 8, iso = 100, pad = 0;
      sscanf(p, "%*s nx=%d ny=%d nz=%d iso=%d pad=%d", &nx, &ny, &nz, &iso, &pad);
      ctx.nx = nx;
      ctx.ny = ny;
      ctx.nz = nz;
      ctx.iso = (uint16_t)iso;
      ctx.pad = pad;
      for (int i = 0; i < nx * ny * nz; i++) {
        ctx.field[i] = 0;
      }
      ms_sync_pad(&ctx);
      continue;
    }
    if (strcmp(kind, "pad") == 0 && n >= 2) {
      ctx.pad = atoi(a + 4);
      ms_sync_pad(&ctx);
      continue;
    }
    if (strcmp(kind, "sphere") == 0) {
      int cx = 0, cy = 0, cz = 0, val = 180;
      double r = 2.0;
      sscanf(p, "%*s cx=%d cy=%d cz=%d r=%lf val=%d", &cx, &cy, &cz, &r, &val);
      fill_sphere(&ctx, cx, cy, cz, r, (uint16_t)val);
      continue;
    }
    if (strcmp(kind, "box") == 0) {
      int x0 = 0, y0 = 0, z0 = 0, x1 = 1, y1 = 1, z1 = 1, val = 50;
      sscanf(p, "%*s x0=%d y0=%d z0=%d x1=%d y1=%d z1=%d val=%d", &x0, &y0, &z0, &x1, &y1, &z1, &val);
      fill_box(&ctx, x0, y0, z0, x1, y1, z1, (uint16_t)val);
      continue;
    }
    if (strcmp(kind, "slab") == 0) {
      int z_end = ctx.z_cursor + 1;
      if (n >= 2 && strncmp(a, "z=", 2) == 0) {
        z_end = atoi(a + 2);
      }
      ctx.slab_z_base = ctx.z_cursor;
      drive_slab(&ctx, z_end);
      continue;
    }
    if (strcmp(kind, "pause") == 0 && pause_mode) {
      ms_pause_leg(&ctx);
      continue;
    }
  }
  fclose(fp);
  fold_nav_digest(&ctx, out->nav_digest, sizeof(out->nav_digest));
  out->polygon_count = ctx.face_n;
  out->portal_count = ctx.face_n;
  out->border_weld_count = fold_border_weld_count(&ctx);
  fold_link_digest(&ctx, out->link_digest, sizeof(out->link_digest));
  out->link_ok = fold_link_ok(&ctx);
  out->area_overlay_ok = (ctx.seam_open_count == 0 && ctx.pad >= 0);

  out->seam_open_count = ctx.seam_open_count;
  strcpy(out->finish_reason, "ok");
  return 0;
}

static int read_schema_anchor(const char *app_root) {
  char path[512];
  snprintf(path, sizeof(path), "%s/stubs/schema_anchor.txt", app_root);
  FILE *fp = fopen(path, "r");
  if (!fp) {
    return SCHEMA_FALLBACK;
  }
  int v = SCHEMA_FALLBACK;
  fscanf(fp, "%d", &v);
  fclose(fp);
  return v;
}

static void write_report(const char *app_root, ms_row *rows, int n_rows, int schema_anchor) {
  char out_path[512];
  snprintf(out_path, sizeof(out_path), "%s/output/nav_audit.json", app_root);
  FILE *fp = fopen(out_path, "w");
  if (!fp) {
    exit(1);
  }
  int pair_fail = 0;
  int link_fail = 0;
  int seam_total = 0;
  for (int i = 0; i + 1 < n_rows; i += 2) {
    ms_row *c = &rows[i];
    ms_row *p = &rows[i + 1];
    int ok = 1;
    if (strcmp(c->nav_digest, p->nav_digest) != 0) {
      ok = 0;
    }
    if (c->polygon_count != p->polygon_count) {
      ok = 0;
    }
    if (c->border_weld_count != p->border_weld_count) {
      ok = 0;
    }
    if (c->link_ok != p->link_ok) {
      ok = 0;
    }
    if (c->seam_open_count != p->seam_open_count) {
      ok = 0;
    }
    if (c->portal_count != p->portal_count) {
      ok = 0;
    }
    if (strcmp(c->link_digest, p->link_digest) != 0) {
      ok = 0;
    }
    if (c->area_overlay_ok != p->area_overlay_ok) {
      ok = 0;
    }
    c->pair_ok = ok;
    p->pair_ok = ok;
    if (!ok) {
      pair_fail++;
    }
    if (!c->link_ok) {
      link_fail++;
    }
    if (!p->link_ok) {
      link_fail++;
    }
    seam_total += c->seam_open_count + p->seam_open_count;
  }
  fprintf(fp, "{\n  \"schema_anchor\": %d,\n  \"scenarios\": [\n", schema_anchor);
  for (int i = 0; i < n_rows; i++) {
    fprintf(fp,
            "    {\"scenario_id\": \"%s\", \"mode\": \"%s\", \"polygon_count\": %d, "
            "\"border_weld_count\": %d, \"nav_digest\": \"%s\", \"portal_count\": %d, "
            "\"link_digest\": \"%s\", \"link_ok\": %s, \"area_overlay_ok\": %s, "
            "\"seam_open_count\": %d, \"pair_ok\": %s, \"finish_reason\": \"%s\"}",
            rows[i].scenario_id, rows[i].mode, rows[i].polygon_count, rows[i].border_weld_count,
            rows[i].nav_digest, rows[i].portal_count, rows[i].link_digest,
            rows[i].link_ok ? "true" : "false", rows[i].area_overlay_ok ? "true" : "false",
            rows[i].seam_open_count,
            rows[i].pair_ok ? "true" : "false", rows[i].finish_reason);
    if (i + 1 < n_rows) {
      fprintf(fp, ",\n");
    } else {
      fprintf(fp, "\n");
    }
  }
  int sc = n_rows / 2;
  fprintf(fp,
          "  ],\n  \"summary\": {\"scenario_count\": %d, \"scenario_rows\": %d, "
          "\"pair_mismatch_count\": %d, \"link_fail_total\": %d, \"seam_open_total\": %d}\n}\n",
          sc, n_rows, pair_fail, link_fail, seam_total);
  fclose(fp);
}

int main(void) {
  const char *app_root = getenv("TASK_APP_ROOT");
  if (!app_root) {
    app_root = APP_ROOT;
  }
  char manifest[512];
  snprintf(manifest, sizeof(manifest), "%s/data/scenarios/manifest.tsv", app_root);
  FILE *mf = fopen(manifest, "r");
  if (!mf) {
    return 1;
  }
  ms_row rows[MAX_SCENARIOS * 2];
  int n_rows = 0;
  char line[256];
  while (fgets(line, sizeof(line), mf)) {
    if (line[0] == '#' || line[0] == '\n') {
      continue;
    }
    char sid[64];
    char tape[128];
    if (sscanf(line, "%63s %127s", sid, tape) != 2) {
      continue;
    }
    char path[512];
    snprintf(path, sizeof(path), "%s/data/tapes/%s.tape", app_root, tape);
    ms_row cont;
    ms_row pause;
    memset(&cont, 0, sizeof(cont));
    memset(&pause, 0, sizeof(pause));
    strncpy(cont.scenario_id, sid, sizeof(cont.scenario_id) - 1);
    strncpy(pause.scenario_id, sid, sizeof(pause.scenario_id) - 1);
    strcpy(cont.mode, "continuous");
    strcpy(pause.mode, "pause_resume");
    if (run_tape(path, 0, &cont) != 0 || run_tape(path, 1, &pause) != 0) {
      fclose(mf);
      return 1;
    }
    rows[n_rows++] = cont;
    rows[n_rows++] = pause;
  }
  fclose(mf);
  char out_dir[512];
  snprintf(out_dir, sizeof(out_dir), "%s/output", app_root);
  mkdir(out_dir, 0755);
  write_report(app_root, rows, n_rows, read_schema_anchor(app_root));
  return 0;
}
