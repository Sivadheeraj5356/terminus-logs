#!/usr/bin/env Rscript

`%||%` <- function(left, right) {
  if (is.null(left)) right else left
}

args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 1) {
  stop("usage: fold_balance.R MANIFEST_PATH")
}

manifest_path <- args[[1]]
manifest <- jsonlite::fromJSON(manifest_path, simplifyVector = FALSE)
folds <- manifest$folds
row_count <- as.numeric(manifest$row_count)

label_columns <- character(0)
global_counts <- list()

for (fold in folds) {
  counts <- fold$label_counts
  if (is.null(counts)) {
    next
  }
  for (label in names(counts)) {
    label_columns <- c(label_columns, label)
    value <- as.numeric(counts[[label]])
    global_counts[[label]] <- (global_counts[[label]] %||% 0) + value
  }
}

label_columns <- sort(unique(label_columns))

max_label_skew <- 0
min_fold_rows <- Inf
max_fold_rows <- 0

for (fold in folds) {
  fold_rows <- length(fold$row_ids)
  min_fold_rows <- min(min_fold_rows, fold_rows)
  max_fold_rows <- max(max_fold_rows, fold_rows)
  for (label in label_columns) {
    count <- 0
    if (!is.null(fold$label_counts) && label %in% names(fold$label_counts)) {
      count <- as.numeric(fold$label_counts[[label]])
    }
    global_prop <- (global_counts[[label]] %||% 0) / row_count
    fold_prop <- if (fold_rows > 0) count / fold_rows else 0
    max_label_skew <- max(max_label_skew, abs(fold_prop - global_prop))
  }
}

payload <- list(
  max_label_skew = max_label_skew,
  min_fold_rows = as.integer(min_fold_rows),
  max_fold_rows = as.integer(max_fold_rows),
  label_columns = label_columns,
  skew_band = if (max_label_skew < 0.05) {
    "tight"
  } else if (max_label_skew < 0.15) {
    "moderate"
  } else {
    "loose"
  }
)

cat(jsonlite::toJSON(payload, auto_unbox = TRUE, digits = 10))
