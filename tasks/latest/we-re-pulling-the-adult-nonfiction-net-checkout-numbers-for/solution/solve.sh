#!/bin/bash
set -euo pipefail

cat > /app/analysis.R <<'RSCRIPT'
#!/usr/bin/env Rscript

suppressPackageStartupMessages({
  library(readr)
  library(dplyr)
  library(jsonlite)
  library(lubridate)
})

lake <- Sys.getenv("DATALAKE_DIR", "/app/data")

FY_START <- "2024-07-01"
FY_END <- "2025-06-30"
FY_TZ <- "America/Chicago"

live_cols <- cols(
  txn_id = col_character(), barcode = col_character(),
  branch_id = col_character(), txn_type = col_character(),
  txn_ts = col_character(), status = col_character(),
  ingest_batch = col_integer()
)

codes <- read_csv(file.path(lake, "item_type_codes.csv"),
                  col_types = cols(item_type_code = col_integer(), collection = col_character(),
                                   description = col_character()))
catalog <- read_tsv(file.path(lake, "catalog_items.tsv"),
                    col_types = cols(barcode = col_character(), item_type_code = col_integer(),
                                     title = col_character(), acquired_date = col_character(),
                                     record_updated = col_character()))
xwalk <- read_csv(file.path(lake, "branch_consolidations.csv"),
                  col_types = cols(retired_branch_id = col_character(),
                                   surviving_branch_id = col_character(),
                                   merged_on = col_character()))
migrated <- read_fwf(
  file.path(lake, "circ_transactions_migrated.txt"),
  fwf_widths(c(10, 14, 4, 12, 20, 4, 3),
             col_names = c("txn_id", "barcode", "branch_id", "txn_type",
                           "txn_ts", "status", "ingest_batch")),
  col_types = cols(txn_id = col_character(), barcode = col_character(),
                   branch_id = col_character(), txn_type = col_character(),
                   txn_ts = col_character(), status = col_character(),
                   ingest_batch = col_integer())
)

live <- bind_rows(
  read_csv(file.path(lake, "circ_transactions_2024.csv"), col_types = live_cols),
  read_csv(file.path(lake, "circ_transactions_2025.csv"), col_types = live_cols),
  migrated
)

catalog_current <- catalog %>%
  arrange(desc(record_updated)) %>%
  distinct(barcode, .keep_all = TRUE)

anf_codes <- codes %>% filter(collection == "ADULT_NONFICTION") %>% pull(item_type_code)
anf_barcodes <- catalog_current %>% filter(item_type_code %in% anf_codes) %>% pull(barcode)

branch_map <- setNames(xwalk$surviving_branch_id, xwalk$retired_branch_id)
resolve_branch <- function(b) ifelse(b %in% names(branch_map), unname(branch_map[b]), b)

live_dedup_fy <- live %>%
  arrange(desc(ingest_batch)) %>%
  distinct(txn_id, .keep_all = TRUE) %>%
  mutate(txn_local = with_tz(ymd_hms(txn_ts, tz = "UTC"), FY_TZ),
         txn_date = format(txn_local, "%Y-%m-%d")) %>%
  filter(txn_date >= FY_START, txn_date <= FY_END)

live_fy <- live_dedup_fy %>% filter(status == "OK")

anf_fy <- live_fy %>% filter(barcode %in% anf_barcodes)

checkouts <- anf_fy %>%
  filter(txn_type == "CHECKOUT") %>%
  mutate(branch_id = resolve_branch(branch_id))

by_branch <- checkouts %>%
  group_by(branch_id) %>%
  summarise(n = n(), .groups = "drop")

by_branch_list <- as.list(setNames(as.integer(by_branch$n), by_branch$branch_id))

result <- list(
  answer = nrow(checkouts),
  by_branch = by_branch_list,
  n_events_fy2024 = nrow(live_dedup_fy),
  n_renewals_excluded = sum(anf_fy$txn_type == "RENEW"),
  n_adult_nonfiction_items = length(unique(anf_barcodes))
)

write_json(result, "/app/answer.json", auto_unbox = TRUE)
RSCRIPT

cd /app
Rscript /app/analysis.R

if [ ! -f /app/answer.json ]; then
  echo "ERROR: /app/answer.json was not produced" >&2
  exit 1
fi

python3 -c "import json,sys; d=json.load(open('/app/answer.json')); req=['answer','by_branch','n_events_fy2024','n_renewals_excluded','n_adult_nonfiction_items']; miss=[k for k in req if k not in d]; sys.exit('ERROR: missing keys '+str(miss)) if miss else print('oracle answer:', d['answer'])"
