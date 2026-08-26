suppressPackageStartupMessages({
  library(readr)
  library(jsonlite)
})

lake_dir <- function() {
  Sys.getenv("DATALAKE_DIR", "/app/data")
}

read_lake_csv <- function(name, ...) {
  read_csv(file.path(lake_dir(), name), show_col_types = FALSE, ...)
}

read_lake_tsv <- function(name, ...) {
  read_tsv(file.path(lake_dir(), name), show_col_types = FALSE, ...)
}

read_lake_json <- function(name) {
  fromJSON(file.path(lake_dir(), name))
}

list_lake_files <- function() {
  sort(list.files(lake_dir()))
}
