neutralize_nonpositive <- function(v) {
  v[!is.na(v) & v <= 0] <- NA
  v
}
