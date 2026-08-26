relative_error <- function(estimate, target) {
  abs(estimate - target) / abs(target)
}

enrolled_fraction <- function(d, treatment = "enrolled") {
  mean(d[[treatment]])
}

standardized_contrast <- function(fit, data, treatment = "enrolled") {
  treated <- data
  treated[[treatment]] <- 1
  control <- data
  control[[treatment]] <- 0
  mean(predict(fit, treated) - predict(fit, control))
}
