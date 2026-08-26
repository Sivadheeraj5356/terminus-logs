load_records <- function(data_dir = Sys.getenv("CAUSAL_DATA_DIR", "/app/data")) {
  baseline <- read.csv(file.path(data_dir, "baseline_covariates.csv"), stringsAsFactors = FALSE)
  tenure <- read.csv(file.path(data_dir, "tenure.csv"), stringsAsFactors = FALSE)
  outreach <- read.csv(file.path(data_dir, "outreach.csv"), stringsAsFactors = FALSE)
  enrollment <- read.csv(file.path(data_dir, "enrollment.csv"), stringsAsFactors = FALSE)
  outcome <- read.csv(file.path(data_dir, "outcome.csv"), stringsAsFactors = FALSE)
  merged <- merge(baseline, tenure, by = "employee_id")
  merged <- merge(merged, outreach, by = "employee_id")
  merged <- merge(merged, enrollment, by = "employee_id")
  merge(merged, outcome, by = "employee_id")
}
