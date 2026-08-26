# Competing-risks modelling and individual risk prediction for the MGUS registry.
# Base R only. Fits cause-specific Breslow Cox models for progression (PCM) and
# death by Newton-Raphson, forms proper competing-risks cumulative-incidence
# predictions for the held-out patients, and reports a reduced block of exact
# marginal estimators. No add-on survival package is required or used.

options(scipen = 999, digits = 15)

data_path <- Sys.getenv("DATA_PATH", unset = "/app/data/registry.csv")
config_path <- Sys.getenv("CONFIG_PATH", unset = "/app/config/analysis.csv")
output_path <- Sys.getenv("OUTPUT_PATH", unset = "/app/outputs")

fail <- function(message) stop(message, call. = FALSE)

if (!file.exists(data_path)) fail(paste("Registry file does not exist:", data_path))
if (!file.exists(config_path)) fail(paste("Configuration does not exist:", config_path))

registry <- read.csv(data_path, stringsAsFactors = FALSE, check.names = FALSE)
config <- read.csv(config_path, stringsAsFactors = FALSE, check.names = FALSE)

req_cols <- c("row_id", "age", "sex", "hgb", "creat", "mspike",
              "ptime", "pstat", "futime", "death")
if (length(setdiff(req_cols, names(registry))) > 0) {
  fail("Registry is missing required columns")
}
registry$sex <- trimws(as.character(registry$sex))
for (column in c("row_id", "age", "hgb", "creat", "mspike",
                 "ptime", "pstat", "futime", "death")) {
  registry[[column]] <- suppressWarnings(as.numeric(registry[[column]]))
}

age_cutpoint <- config$value[config$parameter == "age_cutpoint"][[1]]
horizons <- config$value[config$parameter == "horizon"]
if (length(horizons) != 2) fail("Configuration must contain exactly two horizon rows")

# Held-out patients are exactly the rows whose outcome columns are blank.
held_mask <- is.na(registry$pstat)
active <- registry[!held_mask, , drop = FALSE]
held <- registry[held_mask, , drop = FALSE]
if (nrow(active) == 0) fail("No active (labelled) rows found")

cont_cov <- c("age", "hgb", "creat", "mspike")

# --- disclosed preprocessing: active-median imputation + population z-score ---
med <- vapply(cont_cov, function(c) median(active[[c]], na.rm = TRUE), numeric(1))
impute <- function(df) {
  for (c in cont_cov) df[[c]][is.na(df[[c]])] <- med[[c]]
  df
}
active_i <- impute(active)
held_i <- impute(held)

pop_sd <- function(x) sqrt(mean((x - mean(x))^2))
mu <- vapply(cont_cov, function(c) mean(active_i[[c]]), numeric(1))
sg <- vapply(cont_cov, function(c) {
  s <- pop_sd(active_i[[c]])
  if (s == 0) 1 else s
}, numeric(1))

design <- function(df) {
  cbind(
    age_z = (df$age - mu[["age"]]) / sg[["age"]],
    male = as.numeric(df$sex == "M"),
    hgb_z = (df$hgb - mu[["hgb"]]) / sg[["hgb"]],
    creat_z = (df$creat - mu[["creat"]]) / sg[["creat"]],
    mspike_z = (df$mspike - mu[["mspike"]]) / sg[["mspike"]]
  )
}
Xa <- design(active_i)
Xt <- design(held_i)

# competing-risks event representation on the active rows
cr_setup <- function(df) {
  etime <- ifelse(df$pstat == 1, df$ptime, df$futime)
  event <- ifelse(df$pstat == 1, 1L, ifelse(df$death == 1, 2L, 0L))
  list(etime = etime, event = event)
}
cra <- cr_setup(active)
etime_a <- cra$etime
event_a <- cra$event

# --- cause-specific Breslow Cox by Newton-Raphson --------------------------
cox_breslow <- function(etime, event, X, cause) {
  ev <- as.integer(event == cause)
  times <- sort(unique(etime[ev == 1]))
  p <- ncol(X)
  beta <- rep(0, p)
  info <- diag(p)
  for (iteration in 1:200) {
    eta <- as.vector(X %*% beta)
    w <- exp(eta)
    score <- rep(0, p)
    info <- matrix(0, p, p)
    for (u in times) {
      at_risk <- etime >= u
      Xr <- X[at_risk, , drop = FALSE]
      wr <- w[at_risk]
      s0 <- sum(wr)
      s1 <- as.vector(t(Xr) %*% wr)
      s2 <- t(Xr) %*% (Xr * wr)
      d_idx <- (etime == u) & (ev == 1)
      m <- sum(d_idx)
      if (m == 0) next
      xbar <- s1 / s0
      score <- score + colSums(X[d_idx, , drop = FALSE]) - m * xbar
      info <- info + m * (s2 / s0 - outer(xbar, xbar))
    }
    step <- solve(info, score)
    beta <- beta + step
    if (max(abs(step)) < 1e-12 && max(abs(score)) < 1e-8) break
  }
  # Breslow baseline hazard increments
  w <- exp(as.vector(X %*% beta))
  dl0 <- numeric(length(times))
  for (i in seq_along(times)) {
    u <- times[[i]]
    s0 <- sum(w[etime >= u])
    m <- sum((etime == u) & (ev == 1))
    dl0[[i]] <- m / s0
  }
  list(beta = beta, times = times, dl0 = dl0)
}

pcm_fit <- cox_breslow(etime_a, event_a, Xa, 1L)
death_fit <- cox_breslow(etime_a, event_a, Xa, 2L)

# --- competing-risks CIF prediction with cause-specific feature blocks ------
predict_cif_pcm <- function(fit1, X1, fit2, X2, horizons) {
  all_times <- sort(unique(c(fit1$times, fit2$times)))
  d1 <- setNames(fit1$dl0, as.character(fit1$times))
  d2 <- setNames(fit2$dl0, as.character(fit2$times))
  r1 <- exp(as.vector(X1 %*% fit1$beta))
  r2 <- exp(as.vector(X2 %*% fit2$beta))
  n <- nrow(X1)
  surv <- rep(1, n)
  cif1 <- rep(0, n)
  out <- matrix(0, n, length(horizons))
  n1 <- names(d1)
  n2 <- names(d2)
  for (u in all_times) {
    key <- as.character(u)
    inc1 <- if (key %in% n1) d1[[key]] else 0
    inc2 <- if (key %in% n2) d2[[key]] else 0
    dl1 <- inc1 * r1
    dl2 <- inc2 * r2
    cif1 <- cif1 + surv * dl1
    surv <- surv * (1 - dl1 - dl2)
    for (h in seq_along(horizons)) if (u <= horizons[[h]]) out[, h] <- cif1
  }
  out
}

# Validate each cause's feature family and coefficient scale independently.
# The other cause is held at its full five-covariate fit at scale 1.0 while a
# candidate is scored. This makes the selected rows reproducible and prevents
# the two cause models from being silently coupled through a shared shrinkage.
families <- list(
  core = c(1L, 2L, 4L),
  expanded = c(1L, 2L, 3L, 4L),
  full = 1L:5L
)
family_priority <- c(full = 1L, expanded = 2L, core = 3L)
scales <- c(0.75, 0.9, 1.0, 1.1, 1.25)
fold <- (seq_len(nrow(active)) - 1L) %% 5L
select_spec <- function(cause) {
  candidate_names <- names(families)
  candidate_scores <- numeric(length(candidate_names) * length(scales))
  candidate_model <- character(length(candidate_scores))
  candidate_scale <- numeric(length(candidate_scores))
  pos <- 1L
  for (model_name in candidate_names) {
    cols <- families[[model_name]]
    for (scale in scales) {
      fold_scores <- numeric(5L)
      for (f in 0:4) {
        trn <- fold != f
        val <- fold == f
        candidate_fit <- cox_breslow(
          etime_a[trn], event_a[trn], Xa[trn, cols, drop = FALSE], cause
        )
        other_fit <- cox_breslow(
          etime_a[trn], event_a[trn], Xa[trn, , drop = FALSE], 3L - cause
        )
        candidate_fit$beta <- candidate_fit$beta * scale
        if (cause == 1L) {
          pv <- predict_cif_pcm(
            candidate_fit, Xa[val, cols, drop = FALSE],
            other_fit, Xa[val, , drop = FALSE], horizons
          )
        } else {
          pv <- predict_cif_pcm(
            other_fit, Xa[val, , drop = FALSE],
            candidate_fit, Xa[val, cols, drop = FALSE], horizons
          )
        }
        brier <- numeric(length(horizons))
        for (h in seq_along(horizons)) {
          known <- (event_a[val] > 0) | (etime_a[val] > horizons[[h]])
          y_h <- as.numeric(event_a[val] == 1L & etime_a[val] <= horizons[[h]])
          if (!any(known)) fail("Validation fold has no known horizon status")
          brier[[h]] <- mean((pv[known, h] - y_h[known])^2)
        }
        fold_scores[[f + 1L]] <- mean(brier)
      }
      candidate_model[[pos]] <- model_name
      candidate_scale[[pos]] <- scale
      candidate_scores[[pos]] <- mean(fold_scores)
      pos <- pos + 1L
    }
  }
  best_score <- min(candidate_scores)
  tied <- which(candidate_scores <= best_score + 1e-12)
  tied <- tied[order(
    abs(candidate_scale[tied] - 1.0),
    family_priority[candidate_model[tied]]
  )]
  list(model = candidate_model[[tied[[1]]]],
       scale = candidate_scale[[tied[[1]]]])
}

pcm_spec <- select_spec(1L)
death_spec <- select_spec(2L)
pcm_cols <- families[[pcm_spec$model]]
death_cols <- families[[death_spec$model]]
pcm_pred_fit <- cox_breslow(etime_a, event_a, Xa[, pcm_cols, drop = FALSE], 1L)
death_pred_fit <- cox_breslow(etime_a, event_a, Xa[, death_cols, drop = FALSE], 2L)
pcm_pred_fit$beta <- pcm_pred_fit$beta * pcm_spec$scale
death_pred_fit$beta <- death_pred_fit$beta * death_spec$scale
pred <- predict_cif_pcm(
  pcm_pred_fit, Xt[, pcm_cols, drop = FALSE],
  death_pred_fit, Xt[, death_cols, drop = FALSE], horizons
)
# The discrete Breslow product-limit can drift slightly outside [0, 1) for
# extreme covariate profiles; a cumulative incidence is a probability, so clamp.
pred <- pmin(pmax(pred, 0), 1 - 1e-9)

# --- reduced exact estimators (marginal, on active rows) -------------------
aj_cif <- function(etime, event, cause, horizons) {
  times <- sort(unique(etime[event > 0]))
  surv <- 1
  cif <- 0
  out <- rep(0, length(horizons))
  for (u in times) {
    at_risk <- sum(etime >= u)
    dk <- sum(event == cause & etime == u)
    d_all <- sum(event > 0 & etime == u)
    cif <- cif + surv * (dk / at_risk)
    surv <- surv * (1 - d_all / at_risk)
    for (h in seq_along(horizons)) if (u <= horizons[[h]]) out[[h]] <- cif
  }
  out
}

reverse_km_median <- function(etime, event) {
  cev <- as.integer(event == 0)
  times <- sort(unique(etime[cev == 1]))
  surv <- 1
  m <- NA_real_
  for (u in times) {
    at_risk <- sum(etime >= u)
    dc <- sum(cev == 1 & etime == u)
    surv <- surv * (1 - dc / at_risk)
    if (surv <= 0.5 && is.na(m)) m <- u
  }
  if (is.na(m)) fail("reverse Kaplan-Meier never reaches 0.5")
  m
}

strata <- list(
  overall = active,
  age_low = active[active$age <= age_cutpoint, , drop = FALSE],
  age_high = active[active$age > age_cutpoint, , drop = FALSE]
)

quantity <- character(0)
value <- numeric(0)
add <- function(name, val) {
  quantity[[length(quantity) + 1]] <<- name
  value[[length(value) + 1]] <<- val
}

for (sname in c("overall", "age_low", "age_high")) {
  cr_s <- cr_setup(strata[[sname]])
  for (cause_name in c("pcm", "death")) {
    cause <- if (cause_name == "pcm") 1L else 2L
    vals <- aj_cif(cr_s$etime, cr_s$event, cause, horizons)
    for (h in seq_along(horizons)) {
      add(sprintf("aj_cif_%s_%s_%d", cause_name, sname, as.integer(horizons[[h]])), vals[[h]])
    }
  }
}
add("reverse_km_median", reverse_km_median(etime_a, event_a))
cov_names <- c("age_z", "male", "hgb_z", "creat_z", "mspike_z")
for (i in seq_along(cov_names)) add(paste0("cox_pcm_beta_", cov_names[[i]]), pcm_fit$beta[[i]])
for (i in seq_along(cov_names)) add(paste0("cox_death_beta_", cov_names[[i]]), death_fit$beta[[i]])

estimands <- data.frame(quantity = quantity, value = value, stringsAsFactors = FALSE)

prediction_spec <- data.frame(
  cause = c("PCM", "DEATH"),
  model = c(pcm_spec$model, death_spec$model),
  scale = c(pcm_spec$scale, death_spec$scale),
  stringsAsFactors = FALSE
)

# --- predictions table ------------------------------------------------------
pred_rows <- data.frame(
  row_id = rep(held$row_id, times = length(horizons)),
  horizon_month = rep(as.integer(horizons), each = nrow(held)),
  pcm_prob = as.vector(pred),
  stringsAsFactors = FALSE
)
pred_rows <- pred_rows[order(pred_rows$row_id, pred_rows$horizon_month), , drop = FALSE]

# --- cohort summary (active rows) -------------------------------------------
summary_counts <- list(
  n_active = nrow(active),
  n_heldout = nrow(held),
  n_pcm_active = sum(active$pstat == 1),
  n_death_active = sum(active$pstat == 0 & active$death == 1),
  n_censored_active = sum(active$pstat == 0 & active$death == 0),
  n_male_active = sum(active$sex == "M"),
  n_female_active = sum(active$sex == "F")
)

# --- write deliverables -----------------------------------------------------
dir.create(output_path, recursive = TRUE, showWarnings = FALSE)
if (!dir.exists(output_path)) fail(paste("Could not create output directory:", output_path))

write_fixed_csv <- function(df, path, decimal_cols) {
  out <- df
  for (c in decimal_cols) out[[c]] <- sprintf("%.10f", df[[c]])
  write.table(out, file = path, sep = ",", row.names = FALSE,
              col.names = TRUE, quote = FALSE, na = "")
}

tmp <- file.path(output_path, c(".estimands.csv.tmp", ".prediction_spec.csv.tmp",
                                ".predictions.csv.tmp", ".cohort_summary.json.tmp"))
on.exit(unlink(tmp), add = TRUE)

write_fixed_csv(estimands, tmp[[1]], "value")
write_fixed_csv(prediction_spec, tmp[[2]], "scale")
write_fixed_csv(pred_rows, tmp[[3]], "pcm_prob")

summary_lines <- c("{",
  paste0(vapply(seq_along(summary_counts), function(i) {
    sep <- if (i < length(summary_counts)) "," else ""
    sprintf("  \"%s\": %d%s", names(summary_counts)[[i]], summary_counts[[i]], sep)
  }, character(1)), collapse = "\n"),
  "}")
writeLines(summary_lines, tmp[[4]])

final <- file.path(output_path, c("estimands.csv", "prediction_spec.csv",
                                  "predictions.csv", "cohort_summary.json"))
for (i in seq_along(final)) {
  if (file.exists(final[[i]]) && unlink(final[[i]]) != 0) {
    fail(paste("Could not replace output file:", final[[i]]))
  }
  if (!file.rename(tmp[[i]], final[[i]])) fail(paste("Could not finalize:", final[[i]]))
}
