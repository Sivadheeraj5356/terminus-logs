KIT <- Sys.getenv("APP_KIT", "/app/fskit")
for (f in c("config", "loaders", "encode", "recode", "features",
            "metrics", "cost", "reporting", "serialize", "validate")) {
  source(file.path(KIT, paste0(f, ".R")))
}

FEATURES <- c("job_complexity", "parts_replaced", "prior_tickets_90d",
              "tech_experience_years", "service_month", "qa_signoff_code")
CLASS_COL <- "equipment_class"


build_design <- function(sub, classes) {
  df <- data.frame(row.names = seq_len(nrow(sub)))
  for (c in FEATURES) df[[c]] <- as_num(sub[[c]])
  cls <- clean_text(sub[[CLASS_COL]])
  for (c in classes[-1]) df[[paste0("cls_", c)]] <- as.numeric(cls == c)
  df
}

main <- function() {
  ensure_out_dir()
  raw <- read_ledger()
  require_columns(raw, c(ID_COL, TARGET_COL, PERIOD_COL))
  d <- dedup_by(raw, ID_COL)
  d[[PERIOD_COL]] <- as.integer(as_num(d[[PERIOD_COL]]))
  d[[TARGET_COL]] <- as_num(d[[TARGET_COL]])

  hist <- d[!is.na(d[[TARGET_COL]]), , drop = FALSE]
  pend <- d[d[[PERIOD_COL]] == PENDING_PERIOD, , drop = FALSE]
  classes <- sort(unique(clean_text(hist[[CLASS_COL]])))
  classes <- c(classes[1], classes[-1])

  set.seed(1)
  idx <- sample(nrow(hist))
  cut <- floor(0.8 * nrow(hist))
  tr <- hist[idx[seq_len(cut)], , drop = FALSE]
  va <- hist[idx[(cut + 1):nrow(hist)], , drop = FALSE]

  x_tr <- build_design(tr, classes)
  x_tr$y <- as.integer(tr[[TARGET_COL]])
  model <- glm(y ~ ., data = x_tr, family = binomial())

  pva <- as.numeric(predict(model, newdata = build_design(va, classes), type = "response"))
  yva <- as.integer(va[[TARGET_COL]])
  curve <- sweep_cost(yva, pva)
  thr <- 0.5

  ppe <- as.numeric(predict(model, newdata = build_design(pend, classes), type = "response"))
  ppe <- pmin(pmax(ppe, 0), 1)

  write_predictions(data.frame(
    ticket_id = pend[[ID_COL]],
    repeat_probability = round(ppe, 6),
    dispatch_flag = as.integer(ppe >= thr)
  ))
  write_cost_curve(curve)
  co <- coef(model)
  co <- co[names(co) != "(Intercept)"]
  write_model_terms(names(co), as.numeric(co))
  write_fit_summary(
    c("raw_historical_rows", "unique_tickets", "rows_used"),
    c(nrow(hist), nrow(d), nrow(hist))
  )

  vflag <- as.integer(pva >= thr)
  entries <- list(
    list(key = "n_train", value = nrow(tr), int = TRUE),
    list(key = "n_validation", value = nrow(va), int = TRUE),
    list(key = "n_test", value = nrow(pend), int = TRUE),
    list(key = "train_positive_rate", value = mean(as.integer(tr[[TARGET_COL]]))),
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
