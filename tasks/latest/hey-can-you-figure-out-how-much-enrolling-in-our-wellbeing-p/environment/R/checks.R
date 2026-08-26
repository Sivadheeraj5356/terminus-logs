required_columns <- function() {
  c("employee_id", "age_index", "bmi_index", "activity_index", "chronic_index",
    "diet_index", "sleep_index", "stress_index", "income_index",
    "tenure_years", "outreach_contacts", "enrolled", "wellbeing_index")
}

validate_records <- function(d) {
  missing <- setdiff(required_columns(), names(d))
  if (length(missing) > 0) {
    stop(paste("records are missing columns:", paste(missing, collapse = ", ")))
  }
  if (any(is.na(d))) {
    stop("records contain unexpected missing values")
  }
  if (!all(d$enrolled %in% c(0, 1))) {
    stop("enrolled must be coded 0 or 1")
  }
  invisible(TRUE)
}
