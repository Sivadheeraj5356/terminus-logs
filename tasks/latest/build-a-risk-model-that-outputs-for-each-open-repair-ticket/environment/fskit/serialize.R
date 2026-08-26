write_kv_json <- function(path, entries) {
  fnum <- function(x) formatC(x, format = "f", digits = 6)
  n <- length(entries)
  body <- vapply(seq_len(n), function(i) {
    e <- entries[[i]]
    val <- if (isTRUE(e$int)) sprintf("%d", as.integer(e$value)) else fnum(e$value)
    sep <- if (i < n) "," else ""
    sprintf('  "%s": %s%s', e$key, val, sep)
  }, character(1))
  writeLines(c("{", body, "}"), path)
}
