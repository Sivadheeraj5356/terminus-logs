DATA <- Sys.getenv("APP_DATA", "/app/data/service_ledger.csv")
OUT <- Sys.getenv("APP_OUT", "/app/outputs")

FN_COST <- 5
FP_COST <- 1

PENDING_PERIOD <- 13

ID_COL <- "ticket_id"
PERIOD_COL <- "service_month"
TARGET_COL <- "repeat_visit"

PREDICTIONS_FILE <- "predictions.csv"
COST_CURVE_FILE <- "cost_curve.csv"
MODEL_TERMS_FILE <- "model_terms.csv"
FIT_SUMMARY_FILE <- "fit_summary.csv"
METRICS_FILE <- "metrics.json"
