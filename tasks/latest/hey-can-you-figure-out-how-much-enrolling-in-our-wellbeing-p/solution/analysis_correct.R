data_dir <- Sys.getenv("CAUSAL_DATA_DIR", "/app/data")

baseline <- read.csv(file.path(data_dir, "baseline_covariates.csv"), stringsAsFactors = FALSE)
tenure <- read.csv(file.path(data_dir, "tenure.csv"), stringsAsFactors = FALSE)
outreach <- read.csv(file.path(data_dir, "outreach.csv"), stringsAsFactors = FALSE)
enrollment <- read.csv(file.path(data_dir, "enrollment.csv"), stringsAsFactors = FALSE)
outcome <- read.csv(file.path(data_dir, "outcome.csv"), stringsAsFactors = FALSE)

df <- merge(merge(merge(merge(baseline, tenure, by = "employee_id"),
                        outreach, by = "employee_id"),
                  enrollment, by = "employee_id"),
            outcome, by = "employee_id")

base_cols <- c("age_index", "bmi_index", "activity_index", "chronic_index",
               "diet_index", "sleep_index", "stress_index", "income_index")

A <- as.numeric(df$enrolled)
Y <- as.numeric(df$wellbeing_index)
Xb <- as.matrix(df[, base_cols])
At <- A * df$tenure_years
grid <- seq(0.30, 3.00, by = 0.05)
triples <- combn(length(base_cols), 3)

search_one <- function(fixed) {
  base_design <- cbind(1, A, Xb, df$tenure_years, At)
  if (!is.null(fixed) && ncol(fixed) > 0) base_design <- cbind(base_design, fixed)
  best_rss <- Inf; best_idx <- NULL; best_w <- NA
  for (j in seq_len(ncol(triples))) {
    idx <- triples[, j]
    c1 <- Xb[, idx[1]]; c2 <- Xb[, idx[2]]; c3 <- Xb[, idx[3]]
    for (w in grid) {
      gcol <- sin(w * c1) * sin(w * c2) * sin(w * c3)
      fit <- .lm.fit(cbind(base_design, gcol), Y)
      r <- sum(fit$residuals^2)
      if (r < best_rss) { best_rss <- r; best_idx <- idx; best_w <- w }
    }
  }
  c1 <- Xb[, best_idx[1]]; c2 <- Xb[, best_idx[2]]; c3 <- Xb[, best_idx[3]]
  for (w in seq(best_w - 0.05, best_w + 0.05, by = 0.005)) {
    gcol <- sin(w * c1) * sin(w * c2) * sin(w * c3)
    fit <- .lm.fit(cbind(base_design, gcol), Y)
    r <- sum(fit$residuals^2)
    if (r < best_rss) { best_rss <- r; best_w <- w }
  }
  list(idx = best_idx, w = best_w,
       g = sin(best_w * c1) * sin(best_w * c2) * sin(best_w * c3))
}

first <- search_one(NULL)
second <- search_one(matrix(first$g, ncol = 1))

g1 <- first$g
g2 <- second$g

model_df <- data.frame(Y = Y, A = A, tenure_years = df$tenure_years, g1 = g1, g2 = g2)
model_df <- cbind(model_df, as.data.frame(Xb))
form <- as.formula(paste("Y ~ A + A:tenure_years + tenure_years + g1 + g2 +",
                         paste(base_cols, collapse = " + ")))
fit <- lm(form, data = model_df)

d1 <- model_df; d1$A <- 1
d0 <- model_df; d0$A <- 0
estimate <- mean(predict(fit, d1) - predict(fit, d0))

result <- list(
  estimate = estimate,
  estimand = "population average treatment effect of enrollment on the wellbeing index",
  n_observations = nrow(df),
  recovered_covariates_first = base_cols[first$idx],
  recovered_frequency_first = first$w,
  recovered_covariates_second = base_cols[second$idx],
  recovered_frequency_second = second$w
)

jsonlite::write_json(result, "/app/estimate.json", auto_unbox = TRUE, digits = 10)
