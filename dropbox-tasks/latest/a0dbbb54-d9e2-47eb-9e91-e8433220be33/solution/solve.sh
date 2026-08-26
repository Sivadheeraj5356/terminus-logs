#!/usr/bin/env bash
set -uo pipefail
mkdir -p /app/environment
cat > /app/environment/analysis.R <<'EOF_R'
#!/usr/bin/env Rscript
# Reference solution: cross-conformal p-values with exact rational arithmetic.
# Fractions are (num, den) pairs held in doubles; every integer stays far
# below 2^53, comparisons cross-multiply, and results reduce via gcd.

data_dir <- Sys.getenv("CONFORMAL_DATA_DIR", "/app/environment/data")
out_dir  <- Sys.getenv("CONFORMAL_OUT_DIR", "/app/environment/outputs")
dir.create(out_dir, showWarnings = FALSE, recursive = TRUE)

fgcd <- function(a, b) { a <- abs(a); b <- abs(b); while (b > 0) { t <- a %% b; a <- b; b <- t }; a }
fred <- function(n, d) { if (d < 0) { n <- -n; d <- -d }; g <- fgcd(n, d); if (g > 0) c(n / g, d / g) else c(0, 1) }
fadd <- function(x, y) fred(x[1] * y[2] + y[1] * x[2], x[2] * y[2])
fmul <- function(x, y) fred(x[1] * y[1], x[2] * y[2])
fcmp <- function(x, y) { l <- x[1] * y[2]; r <- y[1] * x[2]; if (l < r) -1 else if (l > r) 1 else 0 }
fmin1 <- function(x) if (fcmp(x, c(1, 1)) > 0) c(1, 1) else x

cells  <- read.csv(file.path(data_dir, "terrain_cells.csv"), colClasses = "character")
labels <- read.csv(file.path(data_dir, "cover_labels.csv"), colClasses = "character")
reg    <- read.csv(file.path(data_dir, "fold_registry.csv"), colClasses = "character")
cal    <- read.csv(file.path(data_dir, "fold_scores_calibration.csv"), colClasses = "character")
ev     <- read.csv(file.path(data_dir, "fold_scores_evaluation.csv"), colClasses = "character")
grid   <- read.csv(file.path(data_dir, "decision_grid.csv"), colClasses = "character")

folds <- sort(unique(as.numeric(ev$fold)))
K <- length(folds)
member_fold <- setNames(as.numeric(reg$fold), reg$cell_id)

cal_fold <- as.numeric(cal$fold)
cal_key <- paste(cal$cell_id, cal$fold)
cal_val <- as.numeric(cal$score_q)
S <- list()
for (k in folds) {
  members <- names(member_fold)[member_fold == k]
  keys <- paste(members, k)
  idx <- match(keys, cal_key)
  S[[as.character(k)]] <- sort(cal_val[idx[!is.na(idx)]])
}

ev_key <- paste(ev$cell_id, ev$fold, ev$class_id)
ev_score <- setNames(as.numeric(ev$score_q), ev_key)
ev_tn <- setNames(as.numeric(ev$theta_num), ev_key)
ev_td <- setNames(as.numeric(ev$theta_den), ev_key)

area_of <- setNames(as.numeric(cells$wilderness_area), cells$cell_id)

p_fold <- function(cell, k, cl) {
  key <- paste(cell, k, cl)
  s <- ev_score[[key]]; tn <- ev_tn[[key]]; td <- ev_td[[key]]
  sc <- S[[as.character(k)]]
  nk <- length(sc)
  if (nk == 0) return(fred(tn, td))
  g <- sum(sc > s)
  e <- sum(sc == s)
  # (g + tn/td * (e+1)) / (nk + 1)  ==  (g*td + tn*(e+1)) / (td*(nk+1))
  fred(g * td + tn * (e + 1), td * (nk + 1))
}

fsort <- function(ps) {
  n <- length(ps)
  if (n <= 1) return(ps)
  for (i in 2:n) {
    key <- ps[[i]]; j <- i - 1
    while (j >= 1 && fcmp(ps[[j]], key) > 0) { ps[[j + 1]] <- ps[[j]]; j <- j - 1 }
    ps[[j + 1]] <- key
  }
  ps
}

combine <- function(ps, rule) {
  kk <- length(ps)
  if (rule == "arith2") {
    tot <- c(0, 1)
    for (p in ps) tot <- fadd(tot, p)
    return(fmin1(fred(2 * tot[1], tot[2] * kk)))
  }
  if (rule == "bonf") {
    mn <- ps[[1]]
    for (p in ps) if (fcmp(p, mn) < 0) mn <- p
    return(fmin1(fred(kk * mn[1], mn[2])))
  }
  if (rule == "median2") {
    srt <- fsort(ps)
    m <- kk %/% 2
    med <- if (kk %% 2 == 1) srt[[m + 1]] else fmul(fadd(srt[[m]], srt[[m + 1]]), c(1, 2))
    return(fmin1(fred(2 * med[1], med[2])))
  }
  stop("unknown rule")
}

pv_rows <- vector("list", nrow(grid) * 7)
diag_keys <- character(0)
diag_sizes <- list()
ri <- 0
for (gi in seq_len(nrow(grid))) {
  rid <- grid$request_id[gi]; cell <- grid$cell_id[gi]
  an <- as.numeric(grid$alpha_num[gi]); ad <- as.numeric(grid$alpha_den[gi])
  rule <- grid$combination_rule[gi]
  alpha <- fred(an, ad)
  setsize <- 0
  for (cl in 1:7) {
    ps <- lapply(folds, function(k) p_fold(cell, k, cl))
    pc <- combine(ps, rule)
    inset <- if (fcmp(pc, alpha) > 0) 1 else 0
    setsize <- setsize + inset
    ri <- ri + 1
    pv_rows[[ri]] <- c(rid, sprintf("%.0f", cl), sprintf("%.0f", pc[1]),
                       sprintf("%.0f", pc[2]), sprintf("%.0f", inset))
  }
  dk <- paste(area_of[[cell]], grid$alpha_num[gi], grid$alpha_den[gi], rule, sep = "|")
  if (!(dk %in% diag_keys)) { diag_keys <- c(diag_keys, dk); diag_sizes[[dk]] <- numeric(0) }
  diag_sizes[[dk]] <- c(diag_sizes[[dk]], setsize)
}

pv <- do.call(rbind, pv_rows)
pv <- pv[order(pv[, 1], as.numeric(pv[, 2])), , drop = FALSE]
pv_df <- data.frame(request_id = pv[, 1], class_id = pv[, 2], p_num = pv[, 3],
                    p_den = pv[, 4], in_set = pv[, 5], stringsAsFactors = FALSE)
write.csv(pv_df, file.path(out_dir, "pvalues.csv"), row.names = FALSE, quote = FALSE)

parts <- strsplit(diag_keys, "|", fixed = TRUE)
dk_area <- as.numeric(vapply(parts, `[`, "", 1))
dk_an <- vapply(parts, `[`, "", 2)
dk_ad <- vapply(parts, `[`, "", 3)
dk_rule <- vapply(parts, `[`, "", 4)
alpha_val <- as.numeric(dk_an) / as.numeric(dk_ad)
ord <- order(dk_area, alpha_val, dk_rule)
rows <- vector("list", length(ord))
for (ii in seq_along(ord)) {
  i <- ord[ii]
  sizes <- diag_sizes[[diag_keys[i]]]
  mean_fr <- fred(sum(sizes), length(sizes))
  rows[[ii]] <- c(sprintf("%.0f", dk_area[i]), dk_an[i], dk_ad[i], dk_rule[i],
                  sprintf("%.0f", mean_fr[1]), sprintf("%.0f", mean_fr[2]))
}
dg <- do.call(rbind, rows)
dg_df <- data.frame(wilderness_area = dg[, 1], alpha_num = dg[, 2],
                    alpha_den = dg[, 3], combination_rule = dg[, 4],
                    mean_setsize_num = dg[, 5], mean_setsize_den = dg[, 6],
                    stringsAsFactors = FALSE)
write.csv(dg_df, file.path(out_dir, "diagnostics.csv"), row.names = FALSE, quote = FALSE)
EOF_R
chmod +x /app/environment/analysis.R
Rscript /app/environment/analysis.R
