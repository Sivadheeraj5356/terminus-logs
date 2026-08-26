write_predictions <- function(df) write_table(df, PREDICTIONS_FILE)

write_cost_curve <- function(df) write_table(df, COST_CURVE_FILE)

write_model_terms <- function(features, importances) {
  mt <- data.frame(
    feature = features,
    importance = round(abs(as.numeric(importances)), 6)
  )
  mt <- mt[order(-mt$importance), ]
  write_table(mt, MODEL_TERMS_FILE)
}

write_fit_summary <- function(metrics, values) {
  write_table(data.frame(metric = metrics, value = values), FIT_SUMMARY_FILE)
}
