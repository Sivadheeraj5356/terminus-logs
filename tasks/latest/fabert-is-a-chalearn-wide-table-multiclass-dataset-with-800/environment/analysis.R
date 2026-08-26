#!/usr/bin/env Rscript

DATA_DIR <- Sys.getenv("DATA_DIR", "/app/data")
OUT_DIR <- Sys.getenv("OUT_DIR", "/app/outputs")
dir.create(OUT_DIR, showWarnings = FALSE, recursive = TRUE)

train_path <- file.path(DATA_DIR, "fabert_train.csv")
score_path <- file.path(DATA_DIR, "fabert_score.csv")

if (!file.exists(train_path) || !file.exists(score_path)) {
  stop("Expected fabert_train.csv and fabert_score.csv under DATA_DIR")
}

train_df <- read.csv(train_path, stringsAsFactors = FALSE)
score_df <- read.csv(score_path, stringsAsFactors = FALSE)

message(sprintf("Loaded %d labelled training rows and %d unlabelled scoring rows.", nrow(train_df), nrow(score_df)))
message("Implement the weighted multiclass pipeline and write the required outputs.")
