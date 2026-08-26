roc_auc <- function(y, p) {
  r <- rank(p)
  n1 <- sum(y == 1)
  n0 <- sum(y == 0)
  if (n1 == 0 || n0 == 0) return(0.5)
  (sum(r[y == 1]) - n1 * (n1 + 1) / 2) / (n1 * n0)
}

pr_auc <- function(y, p) {
  o <- order(p, decreasing = TRUE)
  yl <- y[o]
  tp <- cumsum(yl)
  fp <- cumsum(1 - yl)
  rec <- tp / sum(y)
  prec <- tp / (tp + fp)
  sum(prec * c(rec[1], diff(rec)))
}
