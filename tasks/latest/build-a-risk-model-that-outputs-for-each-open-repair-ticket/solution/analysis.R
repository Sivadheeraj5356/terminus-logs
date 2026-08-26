KIT <- Sys.getenv("APP_KIT", "/app/fskit")
for (f in c("config", "loaders", "encode", "recode", "features",
            "metrics", "cost", "reporting", "serialize", "validate")) {
  source(file.path(KIT, paste0(f, ".R")))
}

NUMS <- c("job_complexity", "parts_replaced", "prior_tickets_90d", "tech_experience_years")
CLASS_COL <- "equipment_class"
RECENT_FROM <- 9
VALID_TOKENS <- c("0", "1", "0.0", "1.0", "", "nan", "none")


clean_ledger <- function(raw) {
  d <- dedup_by(raw, ID_COL)
  d <- d[clean_text(d$record_type) != "qa_audit", , drop = FALSE]
  d[[CLASS_COL]] <- clean_text(d[[CLASS_COL]])
  tok <- clean_text(d[[TARGET_COL]])
  d <- d[tok %in% VALID_TOKENS, , drop = FALSE]
  d[[TARGET_COL]] <- as_num(d[[TARGET_COL]])
  d[[PERIOD_COL]] <- as.integer(as_num(d[[PERIOD_COL]]))
  d$prior_tickets_90d <- neutralize_nonpositive(as_num(d$prior_tickets_90d))
  for (c in NUMS) d[[c]] <- as_num(d[[c]])
  d
}

fit_stats <- function(sub) {
  st <- list()
  for (c in NUMS) {
    v <- as_num(sub[[c]])
    med <- median(v, na.rm = TRUE)
    v[is.na(v)] <- med
    st[[c]] <- list(med = med, mu = mean(v), sd = sd(v))
  }
  st
}

design <- function(sub, st, train_classes, drift, interaction) {
  df <- data.frame(row.names = seq_len(nrow(sub)))
  for (c in NUMS) {
    v <- as_num(sub[[c]])
    v[is.na(v)] <- st[[c]]$med
    df[[c]] <- (v - st[[c]]$mu) / st[[c]]$sd
  }
  logp <- log1p(as_num(sub[[PERIOD_COL]]))
  if (identical(drift, "log")) df[["drift"]] <- logp
  if (identical(drift, "linear")) df[["drift"]] <- as_num(sub[[PERIOD_COL]])
  cls <- clean_text(sub[[CLASS_COL]])
  if (!is.null(train_classes)) {
    for (c in train_classes[-1]) {
      dcol <- as.numeric(cls == c)
      df[[paste0("cls_", c)]] <- dcol
      if (interaction) df[[paste0("cls_", c, "_x_jc")]] <- dcol * df$job_complexity
      if (!is.null(drift)) df[[paste0("cls_", c, "_x_drift")]] <- dcol * df[["drift"]]
    }
  }
  df
}

fit_glm <- function(sub, st, train_classes, drift, interaction) {
  x <- design(sub, st, train_classes, drift, interaction)
  x$y <- as.integer(as_num(sub[[TARGET_COL]]))
  glm(y ~ ., data = x, family = binomial())
}

predict_glm <- function(model, sub, st, train_classes, drift, interaction) {
  x <- design(sub, st, train_classes, drift, interaction)
  as.numeric(predict(model, newdata = x, type = "response"))
}

main <- function() {
  ensure_out_dir()
  df <- read_ledger()
  require_columns(df, c(ID_COL, TARGET_COL, PERIOD_COL))
  raw_rows <- nrow(df[as.integer(as_num(df[[PERIOD_COL]])) < PENDING_PERIOD, , drop = FALSE])

  pend <- df[as.integer(as_num(df[[PERIOD_COL]])) == PENDING_PERIOD, , drop = FALSE]
  pend <- dedup_by(pend, ID_COL)

  clean <- clean_ledger(df)
  hist <- clean[!is.na(clean[[TARGET_COL]]) & clean[[TARGET_COL]] %in% c(0, 1), , drop = FALSE]
  unique_tickets <- nrow(dedup_by(df, ID_COL))
  rows_used <- nrow(hist)

  train_classes <- sort(unique(clean_text(hist[[CLASS_COL]])))
  ref <- train_classes[1]
  train_classes <- c(ref, setdiff(train_classes, ref))

  tr <- hist[hist[[PERIOD_COL]] < RECENT_FROM, , drop = FALSE]
  va <- hist[hist[[PERIOD_COL]] >= RECENT_FROM, , drop = FALSE]
  st_v <- fit_stats(tr)
  m_v <- fit_glm(tr, st_v, train_classes, "log", TRUE)
  pva <- predict_glm(m_v, va, st_v, train_classes, "log", TRUE)
  yva <- as.integer(as_num(va[[TARGET_COL]]))
  curve <- sweep_cost(yva, pva)
  thr <- curve$threshold[which.min(curve$expected_cost)]

  st_f <- fit_stats(hist)
  m_full <- fit_glm(hist, st_f, train_classes, "log", TRUE)
  m_back <- fit_glm(hist, st_f, NULL, "log", FALSE)

  cls_p <- clean_text(pend[[CLASS_COL]])
  known <- cls_p %in% train_classes
  ppe <- numeric(nrow(pend))
  if (any(known)) ppe[known] <- predict_glm(m_full, pend[known, , drop = FALSE], st_f, train_classes, "log", TRUE)
  if (any(!known)) ppe[!known] <- predict_glm(m_back, pend[!known, , drop = FALSE], st_f, NULL, "log", FALSE)
  ppe <- pmin(pmax(ppe, 0), 1)

  write_predictions(data.frame(
    ticket_id = pend[[ID_COL]],
    repeat_probability = round(ppe, 6),
    dispatch_flag = as.integer(ppe >= thr)
  ))
  write_cost_curve(curve)

  co <- coef(m_full)
  co <- co[names(co) != "(Intercept)"]
  write_model_terms(names(co), as.numeric(co))
  write_fit_summary(
    c("raw_historical_rows", "unique_tickets", "rows_used"),
    c(raw_rows, unique_tickets, rows_used)
  )

  vflag <- as.integer(pva >= thr)
  entries <- list(
    list(key = "n_train", value = nrow(tr), int = TRUE),
    list(key = "n_validation", value = nrow(va), int = TRUE),
    list(key = "n_test", value = nrow(pend), int = TRUE),
    list(key = "train_positive_rate", value = mean(as.integer(as_num(tr[[TARGET_COL]])))),
    list(key = "validation_positive_rate", value = mean(yva)),
    list(key = "roc_auc", value = roc_auc(yva, pva)),
    list(key = "pr_auc", value = pr_auc(yva, pva)),
    list(key = "recall", value = sum(vflag == 1 & yva == 1) / max(1, sum(yva == 1))),
    list(key = "threshold", value = thr),
    list(key = "expected_cost", value = cost_of(yva, vflag), int = TRUE),
    list(key = "cost_fn", value = FN_COST, int = TRUE),
    list(key = "cost_fp", value = FP_COST, int = TRUE)
  )
  write_kv_json(file.path(OUT, METRICS_FILE), entries)
}

main()
