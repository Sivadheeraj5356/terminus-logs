#!/usr/bin/env Rscript

## Deployment-calibrated, education-fair subscription scoring under case-control
## training. A pooled logistic model that never reads the protected attribute
## (education) is fit on the enriched training rows; the deployment subscription rate
## is then recovered from the unlabelled held-out contacts by black-box shift
## estimation (invert the training confusion matrix against the held-out
## predicted-label distribution) and the scores are reconciled onto that rate. A
## model left at the enriched training rate reads far too high within every group.

DATA_PATH <- "/app/environment/data/bank_additional.csv"
OUTPUT_DIR <- "/app/environment/outputs"
dir.create(OUTPUT_DIR, showWarnings = FALSE, recursive = TRUE)
d <- read.csv(DATA_PATH, stringsAsFactors = FALSE)

for (col in c("job", "marital", "default", "housing", "loan",
              "contact", "month", "day_of_week", "poutcome")) {
  d[[col]] <- factor(d[[col]], levels = sort(unique(d[[col]])))
}
d$log_camp <- log1p(d$campaign)
d$prev_contact <- as.numeric(d$pdays != 999)
d$pdays_s <- ifelse(d$pdays == 999, 0, d$pdays) / 10
d$log_prev <- log1p(d$previous)

## education is deliberately absent from the model matrix. Natural-spline bases on
## the continuous covariates and quadratic terms on the macro indicators let the
## unaware model rank uniformly across education groups and hold down the
## worst-subgroup discrimination gap, while staying robust to the jittered variant.
X <- model.matrix(
  ~ splines::ns(euribor3m, df = 6) + poly(nr.employed, 2)
    + poly(emp.var.rate, 2) + poly(cons.price.idx, 2)
    + I(age / 10) + I((age / 10)^2) + cons.conf.idx
    + log_camp + I(log_camp^2) + prev_contact + pdays_s + log_prev
    + job + marital + default + housing + loan + contact
    + month + day_of_week + poutcome
    + job:contact + month:poutcome,
  data = d
)

is_train <- d$y %in% c("yes", "no")
train_idx <- which(is_train)
test_idx <- which(!is_train)
ytr <- as.integer(d$y[train_idx] == "yes")

## split train into a fitting fold and a confusion (shift-estimation) fold
nt <- length(train_idx)
cal_mask <- (seq_len(nt) %% 4) == 0
fit_rows <- train_idx[!cal_mask]
cal_rows <- train_idx[cal_mask]
yfit <- as.integer(d$y[fit_rows] == "yes")
ycal <- as.integer(d$y[cal_rows] == "yes")

beta <- {
  f <- suppressWarnings(glm.fit(X[fit_rows, , drop = FALSE], yfit,
                                family = binomial(), control = glm.control(maxit = 100)))
  b <- f$coefficients
  b[is.na(b)] <- 0
  b
}
pr <- function(rows) pmin(pmax(plogis(as.vector(X[rows, , drop = FALSE] %*% beta)), 1e-6), 1 - 1e-6)
p_cal <- pr(cal_rows)
p_test <- pr(test_idx)
pi_train <- mean(yfit)

## black-box shift estimation of the deployment rate
thr <- 0.5
yhat_cal <- as.integer(p_cal >= thr)
Cm <- matrix(0, 2, 2)
for (j in c(0, 1)) {
  sel <- ycal == j
  for (i in c(0, 1)) Cm[i + 1, j + 1] <- mean(yhat_cal[sel] == i)
}
q <- c(mean(p_test < thr), mean(p_test >= thr))
w <- tryCatch(solve(Cm, q), error = function(e) c(1, 1))
pit_vec <- pmax(w * c(1 - pi_train, pi_train), 1e-6)
pid <- min(max(pit_vec[2] / sum(pit_vec), 1e-4), 0.95)

## reconcile: prior-correct to pid, then shift the intercept so the mean equals pid
recon <- function(delta) {
  odds <- (p_test / (1 - p_test)) * (pid / (1 - pid)) * ((1 - pi_train) / pi_train) * exp(delta)
  odds / (1 + odds)
}
f <- function(delta) mean(recon(delta)) - pid
delta <- if (f(-8) * f(8) <= 0) uniroot(f, c(-8, 8), tol = 1e-10)$root else 0
p_final <- pmin(pmax(recon(delta), 1e-6), 1 - 1e-6)

auc_of <- function(y, p) {
  r <- rank(p, ties.method = "average")
  n1 <- sum(y == 1); n0 <- sum(y == 0)
  (sum(r[y == 1]) - n1 * (n1 + 1) / 2) / (n1 * n0)
}
ap_of <- function(y, p) {
  o <- order(-p); ys <- y[o]
  prec <- cumsum(ys) / seq_along(ys)
  sum(prec[ys == 1]) / sum(ys)
}
val_auc <- auc_of(ycal, p_cal)
val_ap <- ap_of(ycal, p_cal)
val_brier <- mean((pr(cal_rows) - ycal)^2)

fmt <- function(x, n) formatC(round(x, n), format = "f", digits = n)
out <- data.frame(row_id = d$row_id[test_idx], pred_proba = fmt(p_final, 6))
out <- out[order(out$row_id), ]
write.csv(out, file.path(OUTPUT_DIR, "predictions.csv"), row.names = FALSE)

metrics <- list(
  n_train = as.character(length(train_idx)),
  n_test = as.character(length(test_idx)),
  roc_auc_val = fmt(val_auc, 6),
  pr_auc_val = fmt(val_ap, 6),
  brier_val = fmt(val_brier, 6),
  n_subgroups = as.character(length(unique(as.character(d$education))))
)
writeLines(
  paste0("{\n",
         paste(sprintf("  \"%s\": \"%s\"", names(metrics), unlist(metrics)), collapse = ",\n"),
         "\n}\n"),
  file.path(OUTPUT_DIR, "metrics.json")
)
