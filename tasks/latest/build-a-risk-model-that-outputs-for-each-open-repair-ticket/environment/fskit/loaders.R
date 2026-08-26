read_ledger <- function(path = DATA) {
  read.csv(path, stringsAsFactors = FALSE, colClasses = "character")
}

write_table <- function(df, name) {
  write.csv(df, file.path(OUT, name), row.names = FALSE)
}

ensure_out_dir <- function(path = OUT) {
  dir.create(path, showWarnings = FALSE, recursive = TRUE)
}
