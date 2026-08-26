write_estimate <- function(estimate, path = "/app/estimate.json", extra = list()) {
  if (!requireNamespace("jsonlite", quietly = TRUE)) {
    stop("jsonlite is required to write the result")
  }
  payload <- c(list(estimate = estimate), extra)
  jsonlite::write_json(payload, path, auto_unbox = TRUE, digits = 10)
  invisible(path)
}
