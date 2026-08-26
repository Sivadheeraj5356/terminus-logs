#!/usr/bin/env Rscript
suppressPackageStartupMessages(library(jsonlite))

data_dir <- "/app/data"
out_dir <- "/app/outputs"
dir.create(out_dir, showWarnings = FALSE, recursive = TRUE)

dat <- read.csv(file.path(data_dir, "climate_crashes.csv"))
fit <- glm(failure ~ ., data = dat, family = binomial(link = "cloglog"))

sm <- summary(fit)$coefficients
terms <- rownames(sm)
predictors <- setdiff(names(dat), "failure")

coef_list <- list()
for (t in terms) {
  coef_list[[t]] <- list(
    estimate = round(unname(sm[t, "Estimate"]), 6),
    std_error = round(unname(sm[t, "Std. Error"]), 6),
    z_value = round(unname(sm[t, "z value"]), 6),
    p_value = round(unname(sm[t, "Pr(>|z|)"]), 8)
  )
}

# Likelihood-ratio test of the whole covariate model against the intercept-only
# null, from the deviance difference on (number of predictors) degrees of freedom.
lr_stat <- fit$null.deviance - fit$deviance
lr_df <- length(predictors)
lr_p <- pchisq(lr_stat, df = lr_df, lower.tail = FALSE)

# Average marginal effect of each predictor on the failure probability: the mean
# over runs of the partial derivative of P(failure) with respect to that predictor.
# For the complementary log-log link P = 1 - exp(-exp(eta)), the derivative is
# beta_k * exp(eta - exp(eta)), averaged over the runs.
eta <- as.numeric(predict(fit, type = "link"))
dens <- exp(eta - exp(eta))
beta <- coef(fit)
ame <- list()
for (pnm in predictors) {
  ame[[pnm]] <- round(unname(beta[pnm]) * mean(dens), 8)
}

# Permutation inference: refit the model under the committed failure-label
# reorderings in permutation_index.csv and build the null distribution of the
# largest predictor coefficient magnitude. The 95th percentile of that null has no
# closed-form shortcut; it can only be produced by running the refits.
perm <- as.matrix(read.csv(file.path(data_dir, "permutation_index.csv")))
B <- nrow(perm)
y <- dat$failure
xdat <- dat[, predictors]
obs_max_abs_coef <- max(abs(beta[predictors]))
perm_stats <- numeric(B)
for (b in seq_len(B)) {
  yb <- y[perm[b, ]]
  fb <- glm(yb ~ ., data = data.frame(yb = yb, xdat),
            family = binomial(link = "cloglog"),
            control = glm.control(maxit = 200, epsilon = 1e-10))
  cb <- coef(fb)
  perm_stats[b] <- max(abs(cb[predictors]))
}
null_q95 <- as.numeric(quantile(perm_stats, 0.95, names = FALSE))

model <- list(
  n_obs = nrow(dat),
  n_events = as.integer(sum(dat$failure)),
  coefficients = coef_list,
  null_deviance = round(fit$null.deviance, 4),
  deviance = round(fit$deviance, 4),
  aic = round(fit$aic, 4),
  lr_statistic = round(lr_stat, 4),
  lr_df = as.integer(lr_df),
  lr_pvalue = round(lr_p, 8),
  average_marginal_effects = ame,
  permutation_test = list(
    n_permutations = as.integer(B),
    observed_max_abs_coef = round(obs_max_abs_coef, 6),
    null_q95_max_abs_coef = round(null_q95, 6)
  )
)
write_json(model, file.path(out_dir, "cloglog_model.json"),
           auto_unbox = TRUE, pretty = TRUE, digits = 10)

fitted_out <- data.frame(row_id = seq_len(nrow(dat)),
                         fitted_prob = round(fitted(fit), 6))
write.csv(fitted_out, file.path(out_dir, "fitted.csv"), row.names = FALSE)

cat("done\n")
