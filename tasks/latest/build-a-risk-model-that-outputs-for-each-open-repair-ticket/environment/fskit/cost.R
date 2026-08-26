cost_of <- function(y, flag, fn = FN_COST, fp = FP_COST) {
  fn * sum(flag == 0 & y == 1) + fp * sum(flag == 1 & y == 0)
}

sweep_cost <- function(y, p, fn = FN_COST, fp = FP_COST) {
  ths <- round(seq(0.02, 0.90, length.out = 89), 4)
  do.call(rbind, lapply(ths, function(th) {
    f <- as.integer(p >= th)
    data.frame(
      threshold = th,
      tp = sum(f == 1 & y == 1), fp = sum(f == 1 & y == 0),
      tn = sum(f == 0 & y == 0), fn = sum(f == 0 & y == 1),
      expected_cost = fn * sum(f == 0 & y == 1) + fp * sum(f == 1 & y == 0)
    )
  }))
}
