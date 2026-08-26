#!/usr/bin/env Rscript

suppressPackageStartupMessages({
  library(readr)
  library(dplyr)
  library(jsonlite)
})

lake <- Sys.getenv("DATALAKE_DIR", "/app/data")

FY_MONTHS_START <- "2024-07"
FY_MONTHS_END <- "2025-06"

rollup <- read_csv(file.path(lake, "circ_monthly_rollup.csv"), show_col_types = FALSE)
catalog <- read_tsv(file.path(lake, "catalog_items.tsv"), show_col_types = FALSE)
codes <- read_csv(file.path(lake, "item_type_codes.csv"), show_col_types = FALSE)

fy <- rollup %>%
  filter(month >= FY_MONTHS_START, month <= FY_MONTHS_END)

by_branch <- fy %>%
  group_by(branch_id) %>%
  summarise(n = sum(checkouts_total), .groups = "drop")

anf_codes <- codes %>% filter(collection == "ADULT_NONFICTION") %>% pull(item_type_code)
n_anf <- catalog %>% filter(item_type_code %in% anf_codes) %>% nrow()

result <- list(
  answer = sum(fy$checkouts_total),
  by_branch = as.list(setNames(as.integer(by_branch$n), by_branch$branch_id)),
  n_events_fy2024 = sum(fy$checkouts_total),
  n_renewals_excluded = 0L,
  n_adult_nonfiction_items = n_anf
)

write_json(result, "/app/answer.json", auto_unbox = TRUE)
