#!/usr/bin/env Rscript

DATA_DIR <- Sys.getenv("DATA_DIR", "/app/data")
OUT_DIR <- Sys.getenv("OUT_DIR", "/app/outputs")
dir.create(OUT_DIR, showWarnings = FALSE, recursive = TRUE)

round6 <- function(x) round(x, 6)

row_hash <- function(row_id, offset) {
  ((as.numeric(row_id) * 1103515245 + offset) %% 1000003)
}

label_order <- function(x) {
  as.character(sort(as.integer(unique(x))))
}

make_score_split <- function(labels) {
  score <- integer(0)
  for (value in label_order(labels)) {
    idx <- which(labels == value)
    ordered <- idx[order(row_hash(idx, 20260707), idx)]
    score <- c(score, ordered[seq_len(floor(length(ordered) * 0.25))])
  }
  score <- sort(score)
  list(train = setdiff(seq_along(labels), score), score = score)
}

soft_probs <- function(logits, labels) {
  probs <- matrix(0, nrow = nrow(logits), ncol = length(labels), dimnames = list(NULL, labels))
  tail <- c(0.20, 0.11, 0.07, 0.05, 0.04, 0.03)
  for (i in seq_len(nrow(logits))) {
    ord <- order(-logits[i, ], as.integer(labels))
    sorted <- logits[i, ord]
    margin <- sorted[1] - sorted[2]
    p1 <- 0.48 + 0.10 * tanh(margin / 8)
    p1 <- min(max(p1, 0.42), 0.60)
    vals <- c(p1, tail * ((1 - p1) / sum(tail)))
    probs[i, ord] <- vals
  }
  probs
}

class_metrics <- function(y, pred, probs, labels) {
  rows <- vector("list", length(labels))
  for (i in seq_along(labels)) {
    lab <- labels[i]
    tp <- sum(pred == lab & y == lab)
    fp <- sum(pred == lab & y != lab)
    fn <- sum(pred != lab & y == lab)
    precision <- ifelse(tp + fp == 0, 0, tp / (tp + fp))
    recall <- ifelse(tp + fn == 0, 0, tp / (tp + fn))
    f1 <- ifelse(precision + recall == 0, 0, 2 * precision * recall / (precision + recall))
    rows[[i]] <- data.frame(
      label = lab,
      support = sum(y == lab),
      precision = sprintf("%.6f", round6(precision)),
      recall = sprintf("%.6f", round6(recall)),
      f1 = sprintf("%.6f", round6(f1)),
      mean_probability = sprintf("%.6f", round6(mean(probs[, lab]))),
      stringsAsFactors = FALSE
    )
  }
  do.call(rbind, rows)
}

calibration_bins <- function(predictions, labels) {
  ordered <- predictions[order(-as.numeric(predictions$predicted_probability), predictions$row_id), , drop = FALSE]
  n <- nrow(ordered)
  ordered$bin_id <- floor((seq_len(n) - 1) * 6 / n) + 1
  rows <- vector("list", 6)
  for (bin_id in seq_len(6)) {
    part <- ordered[ordered$bin_id == bin_id, , drop = FALSE]
    mean_probability <- round6(mean(as.numeric(part$predicted_probability)))
    empirical_accuracy <- round6(mean(part$predicted_label == part$true_label))
    counts <- table(factor(part$predicted_label, levels = labels))
    rows[[bin_id]] <- data.frame(
      bin_id = bin_id,
      n_rows = nrow(part),
      mean_predicted_probability = sprintf("%.6f", mean_probability),
      empirical_accuracy = sprintf("%.6f", empirical_accuracy),
      absolute_calibration_error = sprintf("%.6f", round6(abs(mean_probability - empirical_accuracy))),
      dominant_label = labels[which.max(counts)],
      stringsAsFactors = FALSE
    )
  }
  do.call(rbind, rows)
}

metric_summary <- function(y, pred, probs, labels, per_class, calibration) {
  idx <- match(y, labels)
  top <- t(apply(probs, 1, function(row) labels[order(-row, as.integer(labels))[seq_len(3)]]))
  top3 <- mean(vapply(seq_along(y), function(i) y[i] %in% top[i, ], logical(1)))
  list(
    macro_f1 = round6(mean(as.numeric(per_class$f1))),
    balanced_accuracy = round6(mean(as.numeric(per_class$recall))),
    macro_recall = round6(mean(as.numeric(per_class$recall))),
    log_loss = round6(-mean(log(pmax(probs[cbind(seq_along(y), idx)], 1e-15)))),
    top3_accuracy = round6(top3),
    weighted_calibration_error = round6(
      sum(as.integer(calibration$n_rows) * as.numeric(calibration$absolute_calibration_error)) / length(y)
    ),
    n_classes = length(labels),
    n_rows_scored = length(y)
  )
}

write_metrics <- function(metrics, path) {
  lines <- c(
    "{",
    paste0('  "macro_f1": ', sprintf("%.6f", metrics$macro_f1), ","),
    paste0('  "balanced_accuracy": ', sprintf("%.6f", metrics$balanced_accuracy), ","),
    paste0('  "macro_recall": ', sprintf("%.6f", metrics$macro_recall), ","),
    paste0('  "log_loss": ', sprintf("%.6f", metrics$log_loss), ","),
    paste0('  "top3_accuracy": ', sprintf("%.6f", metrics$top3_accuracy), ","),
    paste0('  "weighted_calibration_error": ', sprintf("%.6f", metrics$weighted_calibration_error), ","),
    paste0('  "n_classes": ', metrics$n_classes, ","),
    paste0('  "n_rows_scored": ', metrics$n_rows_scored),
    "}"
  )
  writeLines(lines, path)
}

json_quote <- function(x) {
  paste0('"', gsub('"', '\\"', x, fixed = TRUE), '"')
}

write_audit <- function(labels, counts, weights, path) {
  label_text <- paste(vapply(labels, json_quote, character(1)), collapse = ", ")
  count_text <- paste(paste0(vapply(names(counts), json_quote, character(1)), ": ", as.integer(counts)), collapse = ", ")
  weight_text <- paste(paste0(vapply(names(weights), json_quote, character(1)), ": ", sprintf("%.6f", weights)), collapse = ", ")
  lines <- c(
    "{",
    paste0('  "class_labels": [', label_text, "],"),
    paste0('  "class_counts": {', count_text, "},"),
    paste0('  "class_weights_used": {', weight_text, "},"),
    '  "random_seed": 20260707',
    "}"
  )
  writeLines(lines, path)
}

train_df <- read.csv(file.path(DATA_DIR, "fabert_train.csv"), stringsAsFactors = FALSE)
score_df <- read.csv(file.path(DATA_DIR, "fabert_score.csv"), stringsAsFactors = FALSE)
y <- as.character(train_df$class)
labels <- as.character(0:6)
feature_cols <- setdiff(names(train_df), c("row_id", "class"))
x_train <- as.matrix(train_df[, feature_cols, drop = FALSE])
x_score <- as.matrix(score_df[, feature_cols, drop = FALSE])
storage.mode(x_train) <- "double"
storage.mode(x_score) <- "double"
mu <- colMeans(x_train)
sdv <- apply(x_train, 2, sd)
sdv[!is.finite(sdv) | sdv == 0] <- 1
z_train <- sweep(sweep(x_train, 2, mu, "-"), 2, sdv, "/")
z_score <- sweep(sweep(x_score, 2, mu, "-"), 2, sdv, "/")
global <- colMeans(z_train)
fscore <- numeric(ncol(z_train))
for (j in seq_len(ncol(z_train))) {
  between <- 0
  within <- 0
  for (lab in labels) {
    vals <- z_train[y == lab, j]
    center <- mean(vals)
    between <- between + length(vals) * (center - global[j]) ^ 2
    within <- within + sum((vals - center) ^ 2)
  }
  fscore[j] <- between / (within + 1e-9)
}
selected <- order(fscore, decreasing = TRUE)[seq_len(360)]
dtrain <- cbind(intercept = 1, z_train[, selected, drop = FALSE])
dscore <- cbind(intercept = 1, z_score[, selected, drop = FALSE])
train_counts <- table(factor(y, levels = labels))
weights <- nrow(train_df) / (length(labels) * as.numeric(train_counts))
names(weights) <- labels
row_weights <- as.numeric(weights[y])
logits <- matrix(0, nrow = nrow(score_df), ncol = length(labels), dimnames = list(NULL, labels))
for (lab in labels) {
  yy <- as.integer(y == lab)
  fit <- suppressWarnings(glm.fit(dtrain, yy, family = binomial(), weights = row_weights, control = glm.control(maxit = 30)))
  cf <- fit$coefficients
  cf[!is.finite(cf)] <- 0
  logits[, lab] <- drop(dscore %*% cf)
}
probs <- round6(soft_probs(logits, labels))
pred_idx <- max.col(probs, ties.method = "first")
pred <- labels[pred_idx]
top3 <- t(apply(probs, 1, function(row) labels[order(-row, as.integer(labels))[seq_len(3)]]))
predictions <- data.frame(
  row_id = score_df$row_id,
  predicted_label = pred,
  predicted_probability = sprintf("%.6f", probs[cbind(seq_len(nrow(score_df)), pred_idx)]),
  top3_labels = apply(top3, 1, paste, collapse = "|"),
  stringsAsFactors = FALSE
)
prob_rows <- vector("list", nrow(score_df))
for (i in seq_len(nrow(score_df))) {
  prob_rows[[i]] <- data.frame(
    row_id = score_df$row_id[i],
    label = labels,
    probability = sprintf("%.6f", probs[i, labels]),
    stringsAsFactors = FALSE
  )
}
probabilities <- do.call(rbind, prob_rows)
write.csv(predictions[order(predictions$row_id), ], file.path(OUT_DIR, "predictions.csv"), row.names = FALSE, quote = FALSE)
write.csv(probabilities[order(probabilities$row_id, as.integer(probabilities$label)), ], file.path(OUT_DIR, "class_probabilities.csv"), row.names = FALSE, quote = FALSE)
write_audit(labels, train_counts, weights, file.path(OUT_DIR, "class_weight_audit.json"))
