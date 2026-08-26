#!/bin/bash
set -euo pipefail
cat > /app/radar_tilt_qc_patch_stack.R <<'RSCRIPT'

MOD <- 1000000007
numstr <- function(x) format(as.numeric(x), scientific = FALSE, trim = TRUE)
hash_items <- function(items) {
  h <- 0
  for (item in items) {
    raw <- charToRaw(enc2utf8(as.character(item)))
    if (length(raw) > 0) {
      for (b in as.integer(raw)) {
        h <- (h * 137 + b) %% MOD
      }
    }
    h <- (h * 137 + 31) %% MOD
  }
  numstr(h)
}
read_trace <- function(path) {
  lines <- readLines(path, warn = FALSE)
  lines <- sub("#.*$", "", lines)
  lines <- trimws(lines)
  lines[nzchar(lines)]
}
fmt_map <- function(values) {
  nms <- sort(names(values))
  nms <- nms[nzchar(nms)]
  if (length(nms) == 0) return("-")
  paste(vapply(nms, function(k) paste0(k, ":", values[[k]]), character(1)), collapse = ";")
}

args <- commandArgs(trailingOnly = TRUE)
if (length(args) != 1) stop("usage: Rscript TOOL TRACE", call. = FALSE)
records <- list()
snapshots <- character()
events <- character()
obs_count <- 0
correction_count <- 0
snap_count <- 0
vacuum_count <- 0
revoke_count <- 0
valid_record <- function(st, en, val, rev) en > st && val > 0 && rev >= 0
zone_load <- function() {
  z <- list()
  for (id in names(records)) {
    rec <- records[[id]]
    z[[rec$zone]] <- (if (is.null(z[[rec$zone]])) 0 else z[[rec$zone]]) + rec$value
  }
  fmt_map(z)
}
active_records <- function() {
  ids <- sort(names(records))
  if (length(ids) == 0) return("-")
  paste(vapply(ids, function(id) { r <- records[[id]]; paste(id, r$start, r$end, r$value, r$zone, r$rev, sep = ":") }, character(1)), collapse = ";")
}
for (line in read_trace(args[1])) {
  parts <- strsplit(line, "\\s+")[[1]]
  op <- parts[1]
  if (op == "OBS" && length(parts) == 7) {
    id <- parts[2]; st <- as.numeric(parts[3]); en <- as.numeric(parts[4]); val <- as.numeric(parts[5]); zone <- parts[6]; rev <- as.numeric(parts[7])
    if (valid_record(st, en, val, rev) && (is.null(records[[id]]) || rev >= records[[id]]$rev)) {
      records[[id]] <- list(start = st, end = en, value = val, zone = zone, rev = rev)
      obs_count <- obs_count + 1
      events <- c(events, paste("obs", id, st, en, val, zone, rev, sep = ":"))
    }
  } else if (op == "CORRECT" && length(parts) == 7) {
    id <- parts[2]; st <- as.numeric(parts[3]); en <- as.numeric(parts[4]); val <- as.numeric(parts[5]); zone <- parts[6]; rev <- as.numeric(parts[7])
    if (!is.null(records[[id]]) && valid_record(st, en, val, rev) && rev >= records[[id]]$rev) {
      records[[id]] <- list(start = st, end = en, value = val, zone = zone, rev = rev)
      correction_count <- correction_count + 1
      events <- c(events, paste("correct", id, st, en, val, zone, rev, sep = ":"))
    }
  } else if (op == "SNAP" && length(parts) == 2) {
    t <- as.numeric(parts[2])
    z <- list()
    for (id in names(records)) {
      r <- records[[id]]
      if (r$start <= t && t < r$end) z[[r$zone]] <- (if (is.null(z[[r$zone]])) 0 else z[[r$zone]]) + r$value
    }
    s <- fmt_map(z)
    snapshots <- c(snapshots, paste(t, s, sep = "|"))
    snap_count <- snap_count + 1
    events <- c(events, paste("snap", t, s, sep = ":"))
  } else if (op == "VACUUM" && length(parts) == 2) {
    cutoff <- as.numeric(parts[2])
    for (id in sort(names(records))) {
      if (!is.null(records[[id]]) && records[[id]]$end <= cutoff) {
        en <- records[[id]]$end
        records[[id]] <- NULL
        vacuum_count <- vacuum_count + 1
        events <- c(events, paste("vacuum", id, en, sep = ":"))
      }
    }
  } else if (op == "REVOKE" && length(parts) == 3) {
    id <- parts[2]; rev <- as.numeric(parts[3])
    if (!is.null(records[[id]]) && rev >= records[[id]]$rev) {
      old <- records[[id]]$rev
      records[[id]] <- NULL
      revoke_count <- revoke_count + 1
      events <- c(events, paste("revoke", id, rev, old, sep = ":"))
    }
  }
}
active_s <- active_records()
zone_s <- zone_load()
snap_s <- if (length(snapshots) == 0) "-" else paste(snapshots, collapse = ";")
latest_rev_sum <- sum(vapply(records, function(r) r$rev, numeric(1)))
pre <- c(active_s, zone_s, snap_s, as.character(obs_count), as.character(correction_count),
         as.character(snap_count), as.character(vacuum_count), as.character(revoke_count),
         as.character(latest_rev_sum))
h <- hash_items(c(pre, events))
out <- c(active_records = active_s, zone_load = zone_s, snapshots = snap_s,
         obs_count = obs_count, correction_count = correction_count, snap_count = snap_count,
         vacuum_count = vacuum_count, revoke_count = revoke_count, latest_rev_sum = latest_rev_sum,
         trace_hash = h)
for (nm in names(out)) cat(nm, "=", out[[nm]], "\n", sep = "")
RSCRIPT
