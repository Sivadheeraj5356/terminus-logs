dedup_by <- function(df, id_col = ID_COL) {
  df[!duplicated(df[[id_col]]), , drop = FALSE]
}

drop_na_rows <- function(df, col) {
  df[!is.na(df[[col]]), , drop = FALSE]
}
