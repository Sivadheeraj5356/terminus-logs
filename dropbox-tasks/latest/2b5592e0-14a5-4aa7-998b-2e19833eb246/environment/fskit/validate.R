require_columns <- function(df, cols) {
  missing <- cols[!cols %in% names(df)]
  if (length(missing) > 0) {
    stop(paste("missing required columns:", paste(missing, collapse = ", ")))
  }
  invisible(df)
}
